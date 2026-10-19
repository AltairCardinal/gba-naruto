/* Finite fixtures only; original bytes execute through pinned mGBA ARM core. */
#include <mgba/flags.h>
#include <mgba/core/config.h>
#include <mgba/core/log.h>
#include <mgba/core/core.h>
#include <mgba/internal/arm/arm.h>
#include <mgba/internal/gba/gba.h>
#include <mgba-util/vfs.h>
#include <mgba-util/sha1.h>
#include <limits.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned current_pc;
static int recording, comma;
static uint32_t (*originalLoad32)(struct ARMCore*,uint32_t,int*);
static uint32_t (*originalLoad16)(struct ARMCore*,uint32_t,int*);
static uint32_t (*originalLoad8)(struct ARMCore*,uint32_t,int*);
static uint32_t (*originalLoadMulti)(struct ARMCore*,uint32_t,int,enum LSMDirection,int*);
static void (*original32)(struct ARMCore*,uint32_t,int32_t,int*);
static void (*original16)(struct ARMCore*,uint32_t,int16_t,int*);
static void (*original8)(struct ARMCore*,uint32_t,int8_t,int*);
static uint32_t (*originalMulti)(struct ARMCore*,uint32_t,int,enum LSMDirection,int*);
static void log_write(unsigned width,unsigned address,unsigned value) {
    if (!recording) return;
    printf("%s[%u,%u,%u,%u]",comma?",":"",current_pc,width,address,value);comma=1;
}
static void store32(struct ARMCore* c,uint32_t a,int32_t v,int* t) {log_write(4,a,(uint32_t)v);original32(c,a,v,t);}
static void store16(struct ARMCore* c,uint32_t a,int16_t v,int* t) {log_write(2,a,(uint16_t)v);original16(c,a,v,t);}
static void store8(struct ARMCore* c,uint32_t a,int8_t v,int* t) {log_write(1,a,(uint8_t)v);original8(c,a,v,t);}
/* Multiple stores are calls, not reconstructed bus events. */
static uint32_t storeMulti(struct ARMCore* c,uint32_t a,int mask,enum LSMDirection d,int* t) {
    if(recording) {
        printf("%s{\"pc\":%u,\"multiple_base\":%u,\"mask\":%u,\"direction\":%u}",comma?",":"",current_pc,a,(unsigned)mask,(unsigned)d);comma=1;
    }
    return originalMulti(c,a,mask,d,t);
}
static void log_read(unsigned width,unsigned address,unsigned value) {
    if(!recording)return;
    printf("%s{\"read\":true,\"pc\":%u,\"width\":%u,\"address\":%u,\"value\":%u}",comma?",":"",current_pc,width,address,value);comma=1;
}
static uint32_t load32(struct ARMCore* c,uint32_t a,int* t) {uint32_t v=originalLoad32(c,a,t);log_read(4,a,v);return v;}
static uint32_t load16(struct ARMCore* c,uint32_t a,int* t) {uint32_t v=originalLoad16(c,a,t);log_read(2,a,v);return v;}
static uint32_t load8(struct ARMCore* c,uint32_t a,int* t) {uint32_t v=originalLoad8(c,a,t);log_read(1,a,v);return v;}
static uint32_t loadMulti(struct ARMCore* c,uint32_t a,int mask,enum LSMDirection d,int* t) {
    if(recording) {printf("%s{\"read\":true,\"pc\":%u,\"multiple_base\":%u,\"mask\":%u,\"direction\":%u}",comma?",":"",current_pc,a,(unsigned)mask,(unsigned)d);comma=1;}
    return originalLoadMulti(c,a,mask,d,t);
}
static int ram(unsigned a,unsigned width) {
    return width && ((a>=0x02000000 && (uint64_t)a+width<=0x02040000)||(a>=0x03000000 && (uint64_t)a+width<=0x03008000));
}
static void fail(const char* s) {fprintf(stderr,"fixture rejected: %s\n",s);exit(3);}
static unsigned read_width(struct mCore* c,unsigned w,unsigned a) {
    if(w==1)return c->busRead8(c,a);
    if(w==2)return c->busRead16(c,a);
    if(w==4)return c->busRead32(c,a);
    fail("read width");return 0;
}
static void write_width(struct mCore* c,unsigned w,unsigned a,unsigned v) {
    if(w==1)c->busWrite8(c,a,v);
    else if(w==2)c->busWrite16(c,a,v);
    else if(w==4)c->busWrite32(c,a,v);
    else fail("write width");
}
static void native_log(struct mLogger* logger,int category,enum mLogLevel level,const char* fmt,va_list args) {
    (void)logger;fprintf(stderr,"mGBA %d %d: ",category,level);vfprintf(stderr,fmt,args);fputc('\n',stderr);
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    struct mLogger logger={.log=native_log};mLogSetDefaultLogger(&logger);
    struct mCore* core=mCoreCreate(mPLATFORM_GBA);if(!core || !core->init(core))fail("init");
    void* video=calloc(256*256,4);if(!video)fail("video allocation");core->setVideoBuffer(core,video,256);
    struct VFile* vf=VFileOpen(argv[1],O_RDONLY);
    if(!vf || !core->loadROM(core,vf))fail("ROM load");
    mCoreConfigInit(&core->config,"finite-arm-probe");
    struct mCoreOptions options={.skipBios=true,.useBios=false,.audioBuffers=1024,.fpsTarget=60,.sampleRate=32768,.volume=0};
    mCoreConfigLoadDefaults(&core->config,&options);mCoreLoadForeignConfig(core,&core->config);core->opts.skipBios=true;core->opts.useBios=false;core->reset(core);
    struct ARMCore* cpu=core->cpu;struct GBA* gba=core->board;
    for(unsigned a=0x02000000;a<0x02040000;a+=4)core->busWrite32(core,a,0);
    for(unsigned a=0x03000000;a<0x03008000;a+=4)core->busWrite32(core,a,0);
    size_t size=core->stateSize(core);void* baseline=calloc(1,size);void* restored=calloc(1,size);
    if(!baseline || !restored || !core->saveState(core,baseline))fail("snapshot save");
    unsigned r0=cpu->gprs[0];core->busWrite32(core,0x03000074,0xA55A5AA5);cpu->gprs[0]=0xDEADBEEF;
    if(!core->loadState(core,baseline)||cpu->gprs[0]!=(int32_t)r0||core->busRead32(core,0x03000074)!=0||!core->saveState(core,restored)||memcmp(baseline,restored,size))fail("snapshot roundtrip");
    uint8_t digest[20];sha1Buffer(baseline,size,digest);
    printf("{\"snapshot_verified\":true,\"state_size\":%zu,\"snapshot_sha1\":\"",size);
    for(unsigned i=0;i<20;++i)printf("%02x",digest[i]);
    printf("\",\"bios_hex\":\"");
    for(unsigned i=0;i<16384;++i)printf("%02x",((unsigned char*)gba->memory.bios)[i]);
    printf("\"}\n");
    original32=cpu->memory.store32;original16=cpu->memory.store16;original8=cpu->memory.store8;originalMulti=cpu->memory.storeMultiple;
    cpu->memory.store32=store32;cpu->memory.store16=store16;cpu->memory.store8=store8;cpu->memory.storeMultiple=storeMulti;
    originalLoad32=cpu->memory.load32;originalLoad16=cpu->memory.load16;originalLoad8=cpu->memory.load8;originalLoadMulti=cpu->memory.loadMultiple;
    cpu->memory.load32=load32;cpu->memory.load16=load16;cpu->memory.load8=load8;cpu->memory.loadMultiple=loadMulti;
    char line[4096];unsigned pw[512],pa[512];int np=0;
    while(fgets(line,sizeof(line),stdin)) {
        char cmd[32],extra;unsigned a,b,n;
        if(sscanf(line,"%31s",cmd)!=1)fail("empty command");
        if(!strcmp(cmd,"begin")) {
            if(strcmp(line,"begin\n"))fail("begin format");
            if(!core->loadState(core,baseline))fail("snapshot restore");
            cpu->cycles=0;cpu->nextEvent=INT32_MAX;np=0;
        } else if(!strcmp(cmd,"reg")) {
            if(sscanf(line,"reg %u %u %c",&n,&a,&extra)!=2 || n>14)fail("register");cpu->gprs[n]=(int32_t)a;
        } else if(!strcmp(cmd,"cpsr")) {
            if(sscanf(line,"cpsr %u %c",&a,&extra)!=1 || !core->writeRegister(core,"cpsr",a))fail("cpsr");
        } else if(!strcmp(cmd,"spsr")) {
            if(sscanf(line,"spsr %u %c",&a,&extra)!=1)fail("spsr");cpu->spsr.packed=a;
        } else if(!strcmp(cmd,"mem")) {
            if(sscanf(line,"mem %u %u %u %c",&n,&a,&b,&extra)!=3 || (n!=1&&n!=2&&n!=4)||!ram(a,n)||a%n)fail("RAM fixture");write_width(core,n,a,b);
        } else if(!strcmp(cmd,"io")) {
            if(sscanf(line,"io %u %u %c",&a,&b,&extra)!=2 || (a!=6&&a!=0x200&&a!=0x202&&a!=0x208)||b>65535)fail("internal readonly IO fixture");gba->memory.io[a/2]=(uint16_t)b;
        } else if(!strcmp(cmd,"copy")) {
            if(sscanf(line,"copy %u %u %u %c",&a,&b,&n,&extra)!=3 || a<0x08000000 || (uint64_t)a+n>0x08600000||!ram(b,n)||n>1024)fail("copy fixture");
            for(unsigned i=0;i<n;++i)core->busWrite8(core,b+i,core->busRead8(core,a+i));
            for(unsigned i=0;i<n;++i)if(core->busRead8(core,b+i)!=core->busRead8(core,a+i))fail("copy readback");
        } else if(!strcmp(cmd,"peek")) {
            if(sscanf(line,"peek %u %u %c",&n,&a,&extra)!=2||np==512||(n!=1&&n!=2&&n!=4)||!ram(a,n)||a%n)fail("peek");pw[np]=n;pa[np++]=a;
        } else if(!strcmp(cmd,"run")) {
            unsigned budget,count,root,stop,lo[8],hi[8];int off;
            if(sscanf(line,"run %u %u %u %u%n",&root,&stop,&budget,&count,&off)!=4||!count||count>8||!budget||budget>2000)fail("run header");
            char* rest=line+off;
            for(unsigned i=0;i<count;++i) {
                if(sscanf(rest," %u %u%n",&lo[i],&hi[i],&off)!=2||lo[i]>=hi[i])fail("run range");rest+=off;
                if(stop>=lo[i]&&stop<hi[i])fail("stop aliases source");
            }
            if(sscanf(rest," %c",&extra)==1)fail("run tail");
            if(!core->writeRegister(core,"pc",root))fail("PC write");
            unsigned visited[2000],steps=0;int status=0;printf("{\"writes\":[");recording=1;comma=0;
            for(;steps<budget;++steps) {
                current_pc=(unsigned)cpu->gprs[15]-(cpu->executionMode==MODE_THUMB?2:4);
                if(current_pc==stop){status=1;break;}
                int allowed=0;
                for(unsigned i=0;i<count;++i)if(current_pc>=lo[i]&&current_pc+(cpu->executionMode==MODE_THUMB?2u:4u)<=hi[i])allowed=1;
                if(!allowed){status=2;break;}visited[steps]=current_pc;core->step(core);
                if(cpu->cycles>=1000000){status=4;++steps;break;}
            }
            recording=0;
            printf("],\"status\":%d,\"stop\":%u,\"cpsr\":%u,\"spsr\":%u,\"visited\":[",status,current_pc,(unsigned)cpu->cpsr.packed,(unsigned)cpu->spsr.packed);
            for(unsigned i=0;i<steps;++i)printf("%s%u",i?",":"",visited[i]);printf("],\"registers\":[");
            for(unsigned i=0;i<16;++i)printf("%s%u",i?",":"",(unsigned)cpu->gprs[i]);printf("],\"peek\":[");
            for(int i=0;i<np;++i)printf("%s[%u,%u,%u]",i?",":"",pa[i],pw[i],read_width(core,pw[i],pa[i]));printf("]}\n");
            if(status!=1)fail("execution escaped or exhausted");
        } else fail("unknown command");
    }
    free(baseline);free(restored);core->deinit(core);free(video);return 0;
}
