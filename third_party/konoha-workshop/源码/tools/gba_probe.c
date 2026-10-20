#include <mgba/flags.h>
#include <mgba/core/core.h>
#include <mgba/core/config.h>
#include <mgba/core/log.h>
#include <mgba/internal/arm/arm.h>
#include <mgba-util/vfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void quiet_log(struct mLogger *l,int category,enum mLogLevel level,const char *fmt,va_list args) {
    (void)l;(void)category;
    static unsigned count;
    if((level==mLOG_FATAL || level==mLOG_ERROR) && count++<20){vfprintf(stderr,fmt,args);fputc('\n',stderr);}
}

/* Local research harness. Saves are explicitly loaded as temporary copies. */
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    struct mLogger logger={.log=quiet_log,.filter=NULL};mLogSetDefaultLogger(&logger);
    struct mCore *c=mCoreFind(argv[1]);
    if (!c || !c->init(c)) return 3;
    mCoreInitConfig(c,"naruto-local-research");
    mCoreConfigSetDefaultIntValue(&c->config,"volume",0);
    mCoreLoadConfig(c);
    mColor *pixels=calloc(256*256,sizeof(mColor));
    c->setVideoBuffer(c,pixels,256);
    if (!mCoreLoadFile(c,argv[1])) return 4;
    if (argc>2 && !mCoreLoadSaveFile(c,argv[2],true)) return 5;
    c->reset(c);
    char line[4096],op[32],path[3072];
    setvbuf(stdout,NULL,_IOLBF,0);
    puts("READY");
    while (fgets(line,sizeof(line),stdin)) {
        unsigned a=0,n=0,k=0,v=0;
        if(sscanf(line,"%31s",op)!=1) continue;
        if(!strcmp(op,"frames")) {
            sscanf(line,"%*s %u %x",&n,&k);
            c->setKeys(c,k); for(unsigned i=0;i<n;i++)c->runFrame(c);
            c->setKeys(c,0); printf("FRAME %u\n",c->frameCounter(c));
        } else if(!strcmp(op,"shot")) {
            if(sscanf(line,"%*s %3071[^\n]",path)!=1)continue;
            struct VFile *f=VFileOpen(path,O_CREAT|O_TRUNC|O_WRONLY);
            bool ok=f&&mCoreTakeScreenshotVF(c,f);if(f)f->close(f);
            printf("SHOT %d\n",ok);
        } else if(!strcmp(op,"dump")) {
            if(sscanf(line,"%*s %x %x %3071[^\n]",&a,&n,path)!=3)continue;
            FILE *f=fopen(path,"wb");if(!f){puts("ERR FILE");continue;}
            for(unsigned i=0;i<n;i++)fputc(c->busRead8(c,a+i),f);
            fclose(f);printf("DUMP %08X %X\n",a,n);
        } else if(!strcmp(op,"read")) {
            sscanf(line,"%*s %x %x",&a,&n);
            for(unsigned i=0;i<n;i++)printf("%02X",c->busRead8(c,a+i)); puts("");
        } else if(!strcmp(op,"w8")||!strcmp(op,"w16")||!strcmp(op,"w32")) {
            sscanf(line,"%*s %x %x",&a,&v);
            if(!strcmp(op,"w8"))c->busWrite8(c,a,v);
            if(!strcmp(op,"w16"))c->busWrite16(c,a,v);
            if(!strcmp(op,"w32"))c->busWrite32(c,a,v);
            puts("WRITE OK");
        } else if(!strcmp(op,"state")||!strcmp(op,"loadstate")) {
            if(sscanf(line,"%*s %3071[^\n]",path)!=1)continue;
            bool save=!strcmp(op,"state");size_t size=c->stateSize(c);
            void *buf=malloc(size);FILE *f=fopen(path,save?"wb":"rb");bool ok=false;
            if(f){if(save){ok=c->saveState(c,buf);if(ok)ok=fwrite(buf,1,size,f)==size;}
            else if(fread(buf,1,size,f)==size)ok=c->loadState(c,buf);fclose(f);}
            free(buf);printf("STATE %d %zu\n",ok,size);
        } else if(!strcmp(op,"savecopy")) {
            if(sscanf(line,"%*s %3071[^\n]",path)!=1)continue;
            void *buf=NULL;size_t size=c->savedataClone(c,&buf);FILE *f=fopen(path,"wb");
            if(f){fwrite(buf,1,size,f);fclose(f);}free(buf);printf("SAVE %zu\n",size);
        } else if(!strcmp(op,"regs")) {
            struct ARMCore *cpu=c->cpu;
            for(unsigned i=0;i<16;i++)printf("r%u=%08X ",i,cpu->gprs[i]);
            printf("cpsr=%08X mode=%d\n",cpu->cpsr.packed,cpu->executionMode);
        } else if(!strcmp(op,"call")) {
            unsigned r0=0,r1=0,r2=0,r3=0;
            sscanf(line,"%*s %x %x %x %x %x",&a,&r0,&r1,&r2,&r3);
            struct ARMCore *cpu=c->cpu;
            unsigned pc=cpu->gprs[15]-(cpu->executionMode?2:4);
            c->writeRegister(c,"r0",r0);c->writeRegister(c,"r1",r1);
            c->writeRegister(c,"r2",r2);c->writeRegister(c,"r3",r3);
            c->writeRegister(c,"lr",pc|(cpu->executionMode?1:0));
            c->writeRegister(c,"pc",a);printf("CALL %08X return=%08X\n",a,pc);
        } else if(!strcmp(op,"reg")) {
            char name[32];if(sscanf(line,"%*s %31s %x",name,&v)==2)
            printf("REG %d\n",c->writeRegister(c,name,v));
        } else if(!strcmp(op,"until")) {
            sscanf(line,"%*s %x %u %x",&a,&n,&k);
            unsigned start=c->frameCounter(c);struct ARMCore *cpu=c->cpu;c->setKeys(c,k);
            unsigned long long steps=0;
            while(c->frameCounter(c)-start<n && steps++<100000000ULL){unsigned pc=cpu->gprs[15]-(cpu->executionMode?2:4);if(pc==a || pc>=0x10000000)break;c->step(c);}
            c->setKeys(c,0);printf("UNTIL frame=%u pc=%08X\n",c->frameCounter(c),cpu->gprs[15]-(cpu->executionMode?2:4));
        } else if(!strcmp(op,"steps")) {
            sscanf(line,"%*s %u",&n);for(unsigned i=0;i<n;i++)c->step(c);puts("STEPS OK");
        } else if(!strcmp(op,"trace")) {
            if(sscanf(line,"%*s %u %3071[^\n]",&n,path)!=2)continue;
            FILE *f=fopen(path,"w");struct ARMCore *cpu=c->cpu;
            uint32_t ring[64][17];unsigned count=0;
            for(unsigned i=0;i<n;i++){
                unsigned pc=cpu->gprs[15]-(cpu->executionMode?2:4);
                ring[count%64][0]=pc;for(unsigned j=0;j<16;j++)ring[count%64][j+1]=cpu->gprs[j];count++;
                if((pc>=0x08097280&&pc<0x08097538)||(pc>=0x08600680&&pc<0x08600750)){
                    fprintf(f,"pc=%08X r0=%08X r1=%08X r2=%08X sp=%08X lr=%08X\n",pc,cpu->gprs[0],cpu->gprs[1],cpu->gprs[2],cpu->gprs[13],cpu->gprs[14]);
                }
                if(pc>=0x10000000)break;
                c->step(c);
            }
            fputs("LAST INSTRUCTIONS\n",f);
            for(unsigned i=count>64?count-64:0;i<count;i++){
                uint32_t *r=ring[i%64];fprintf(f,"pc=%08X ",r[0]);for(unsigned j=0;j<16;j++)fprintf(f,"r%u=%08X ",j,r[j+1]);fputc('\n',f);
            }
            fclose(f);printf("TRACE %u pc=%08X\n",count,cpu->gprs[15]-(cpu->executionMode?2:4));
        } else if(!strcmp(op,"quit"))break;
        else puts("ERR COMMAND");
    }
    c->deinit(c);free(pixels);return 0;
}
