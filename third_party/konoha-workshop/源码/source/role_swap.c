#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define R16(a) (*(volatile u16*)(a))
#define R32(a) (*(volatile u32*)(a))
#define R8(a) (*(volatile u8*)(a))
#define ROMFN(a,t) ((t)((a)|1))
#define PARTY ((volatile u8*)0x02022e34)
#define MAP ((volatile u8*)0x02022ea4)
#define MAGIC (*(volatile u32*)0x02022ea0)
#define TAG 0x33544b4e
#define INIT_MODE (*(volatile u32*)0x0203f000)
#define INIT_CHOICES ((volatile u8*)0x0203f004)
#define MAGIC_INIT 0x494e4b54

extern const u16 ui_header[240*24];
extern const u16 ui_labels[3][96*16];
extern const u16 ui_footer[240*28];
extern u32 native_init(void);
extern u32 native_add(u32,u32);
extern u32 native_story(u32,u32,u32);
extern u32 native_reward(u32,u32,void*);
extern u32 native_auto_skills(volatile u8*,u8*);
extern u32 native_item_compatible(u32,u32);

static unsigned map_role(unsigned id){return MAGIC==TAG && id>=1 && id<=21 ? MAP[id-1] : id;}
static unsigned inverse_role(unsigned id){
    if(MAGIC==TAG && id>=1 && id<=21){for(unsigned i=0;i<21;i++)if(MAP[i]==id)return i+1;}
    return id;
}
/* The unmodified story only permits the original trio to level up. */
unsigned progression_allowed(unsigned cid){
    if(ROMFN(0x08097130,u32(*)(void))())return 1;
    if(MAGIC==TAG)return cid==MAP[0] || cid==MAP[1] || cid==MAP[2];
    return cid>=1 && cid<=3;
}
unsigned story_actor(unsigned cid){return map_role(cid);}
/* Owner zero is the bag; older SAVs can also retain original-trio owners. */
unsigned equipment_owner_allowed(unsigned cid){
    return cid<=3 || progression_allowed(cid);
}
u32 hook_item_compatible(unsigned cid,unsigned item){
    if(native_item_compatible(cid,item))return 1;
    unsigned role=inverse_role(cid);
    if(MAGIC==TAG && role>=1 && role<=3 && role!=cid)
        return native_item_compatible(role,item);
    return 0;
}
static unsigned unique_id(unsigned cid){
    if(cid<1 || cid>21)return 0;
    const u8 *p=(const u8*)(0x0854241c+cid*0xb4+0x48);
    for(unsigned i=0;i<24;i++,p+=4)if(p[0]>23)return p[0];
    return 0;
}
static void special_level(volatile u8 *p,unsigned level){
    for(unsigned i=0;i<24;i++)if(p[0x50+i*4]>23 && p[0x50+i*4]!=255)p[0x51+i*4]=level;
}

static void rect(unsigned x,unsigned y,unsigned w,unsigned h,u16 color){
    volatile u16 *v=(volatile u16*)0x06000000;
    for(unsigned j=0;j<h;j++)for(unsigned i=0;i<w;i++)v[(y+j)*240+x+i]=color;
}
static void bitmap(unsigned x,unsigned y,unsigned w,unsigned h,const u16 *p){
    volatile u16 *v=(volatile u16*)0x06000000;
    for(unsigned j=0;j<h;j++)for(unsigned i=0;i<w;i++)v[(y+j)*240+x+i]=*p++;
}
static void glyph(unsigned x,unsigned y,unsigned code,u16 color){
    const u8 *p=0;
    for(unsigned i=0;i<31;i++){
        const u8 *r=(const u8*)(0x0853d644+i*8);unsigned start=*(const u16*)r;
        if(code>=start && code<start+r[2]){p=*(const u8* const*)(r+4)+(code-start)*32;break;}
    }
    if(!p)return;
    volatile u16 *v=(volatile u16*)0x06000000;
    for(unsigned j=0;j<32;j++)for(unsigned k=0;k<4;k++)
        if((p[j]>>(k*2))&3)v[(y+j/2)*240+x+(j%2)*4+k]=color;
}
static void name(unsigned x,unsigned y,unsigned cid,u16 color){
    const u8 *p=((const u8* const*)0x08599280)[cid];
    while(*p){unsigned c=*p++;if(c>=0x80)c=(c<<8)|*p++;glyph(x,y,c,color);x+=9;}
}
static void wait_vblank(void){while(R16(0x04000006)>=160){}while(R16(0x04000006)<160){}}
static void choose(u8 out[3]){
    u16 ime=R16(0x04000208),disp=R16(0x04000000);
    u16 blend=R16(0x04000050),alpha=R16(0x04000052),fade=R16(0x04000054);
    u32 dma[12];R16(0x04000208)=0;
    for(unsigned i=0;i<4;i++){
        dma[i*3]=R32(0x040000b0+i*12);dma[i*3+1]=R32(0x040000b4+i*12);
        dma[i*3+2]=R32(0x040000b8+i*12);R16(0x040000ba+i*12)=0;
    }
    R16(0x04000050)=0;R16(0x04000052)=0;R16(0x04000054)=0;
    R16(0x04000000)=0x0403;
    out[0]=1;out[1]=2;out[2]=3;
    unsigned row=0,prev=0x3ff,ticks=0,dirty=1;
    for(;;){
        if(dirty){
            rect(0,0,240,160,0x1022);bitmap(0,0,240,24,ui_header);
            for(unsigned i=0;i<3;i++){
                rect(4,28+i*32,232,29,i==row?0x2966:0x1843);
                bitmap(9,35+i*32,96,16,ui_labels[i]);
                name(112,34+i*32,out[i],i==row?0x03ff:0x7fff);
                if(i==row){rect(224,39+i*32,4,6,0x03ff);}
            }
            bitmap(0,131,240,28,ui_footer);dirty=0;
        }
        wait_vblank();unsigned held=(~R16(0x04000130))&0x3ff;
        unsigned press=held&~prev;prev=held;
        if(held&(16|32|64|128)){if(++ticks>=18){press|=held&(16|32|64|128);ticks=13;}}else ticks=0;
        if(press&64){row=(row+2)%3;dirty=1;}
        if(press&128){row=(row+1)%3;dirty=1;}
        if(press&(16|32)){
            unsigned c=out[row];
            do{c=(press&16)?(c==21?1:c+1):(c==1?21:c-1);}while(c==out[(row+1)%3]||c==out[(row+2)%3]);
            out[row]=c;dirty=1;
        }
        if(press&1){row=(row+1)%3;dirty=1;}
        if(press&8)break;
    }
    R16(0x04000000)=0x0080;
    /* The native new-game path recreates its display after this returns. */
    for(unsigned i=0;i<4;i++){
        /* DMA source/destination are write-only. Their original registers were not changed. */
        R32(0x040000b8+i*12)=dma[i*3+2];
    }
    R16(0x04000050)=blend;R16(0x04000052)=alpha;R16(0x04000054)=fade;
    R16(0x04000000)=disp;R16(0x04000208)=ime;
}

u32 hook_init(void){
    u8 selected[3];choose(selected);
    INIT_MODE=MAGIC_INIT;for(unsigned i=0;i<3;i++)INIT_CHOICES[i]=selected[i];
    u32 result=native_init();
    for(unsigned i=0;i<21;i++)MAP[i]=i+1;
    for(unsigned role=0;role<3;role++){
        unsigned at=0;while(at<21 && MAP[at]!=selected[role])at++;
        unsigned tmp=MAP[role];MAP[role]=MAP[at];MAP[at]=tmp;
    }
    MAGIC=TAG;INIT_MODE=0;return result;
}

u32 hook_add(unsigned cid,unsigned level){
    unsigned actual=cid;
    if(INIT_MODE==MAGIC_INIT && cid==1)actual=INIT_CHOICES[0];
    u32 slot=native_add(actual,level);
    if(slot && (MAGIC==TAG || INIT_MODE==MAGIC_INIT)){
        unsigned third=MAGIC==TAG?MAP[2]:INIT_CHOICES[2];
        volatile u8 *p=PARTY+slot*0xbc;
        if(actual==third)special_level(p,1);
        else if(actual==1 || actual==2 || actual==3 || actual==map_role(1) || actual==map_role(2) || INIT_MODE==MAGIC_INIT)special_level(p,255);
    }
    return slot;
}

u32 hook_story(unsigned action,unsigned cid,unsigned level){
    unsigned actual=map_role(cid);
    if(actual==cid)return native_story(action,cid,level);
    if(!action)return native_story(0,actual,level);
    if(!ROMFN(0x08091fe0,u32(*)(u32))(actual))hook_add(actual,level);
    ROMFN(0x08097578,void(*)(u32,u32))(1,actual);
    return 1;
}

unsigned remap_story_stat(unsigned stat){
    if(MAGIC==TAG && stat>=24 && stat<=26)stat=unique_id(MAP[stat-24]);
    return stat;
}

u32 hook_reward(unsigned kind,unsigned stat,void *window){
    if(kind==3)stat=remap_story_stat(stat);
    return native_reward(kind,stat,window);
}

/* Automatic level skills must not bypass a story/scroll unique-ability lock. */
u32 hook_auto_skills(volatile u8 *actor,u8 *list){
    u8 locked[24];
    for(unsigned i=0;i<24;i++)locked[i]=MAGIC==TAG && actor[0x50+i*4]>23 && actor[0x50+i*4]<255 && actor[0x51+i*4]==255;
    u32 result=native_auto_skills(actor,list);
    for(unsigned i=0;i<24;i++)if(locked[i]){
        if(actor[0x51+i*4]!=255)result--;
        actor[0x51+i*4]=255;
        if(list){
            unsigned n=0;
            while(list[n]!=255){
                if(list[n]==(actor[0x50+i*4]|128)){
                    for(unsigned j=n;;j++){list[j]=list[j+1];if(list[j]==255)break;}
                    break;
                }
                n++;
            }
        }
    }
    return result;
}

/* Only the fixed friendly stage-entry branch uses this hook. Enemy IDs and
 * already-resolved party slot references remain native. */
__attribute__((naked,used)) void hook_fixed_ally(void){
    __asm__ volatile(
        "push {r1,r2,lr}\nldrb r0,[r5]\nbl story_actor\nmov r3,r0\npop {r1,r2}\nadd sp,#4\n"
        "movs r0,#188\nmul r0,r4\nadd r0,r8\nldrb r0,[r0,#4]\n"
        "cmp r0,r3\nbne 1f\nldr r3,2f\nbx r3\n1:ldr r3,3f\nbx r3\n.balign 4\n2:.word 0x0806e303\n3:.word 0x0806e2eb");
}
__attribute__((naked,used)) void hook_level_popup(void){
    __asm__ volatile(
        "mov r7,r0\npush {r1,r2,lr}\nldrb r0,[r7]\nbl progression_allowed\npop {r1,r2}\nadd sp,#4\n"
        "cmp r0,#0\nbeq 1f\nldr r3,2f\nbx r3\n1:ldr r3,3f\nbx r3\n.balign 4\n2:.word 0x0808928d\n3:.word 0x080892f7");
}
__attribute__((naked,used)) void hook_level_check(void){
    __asm__ volatile(
        "push {r1,r2,lr}\nldrb r0,[r4]\nbl progression_allowed\npop {r1,r2}\nadd sp,#4\n"
        "cmp r0,#0\nbeq 1f\nldr r3,2f\nbx r3\n1:ldr r3,3f\nbx r3\n.balign 4\n2:.word 0x08089993\n3:.word 0x080899e1");
}
__attribute__((naked,used)) void hook_exp_display(void){
    __asm__ volatile(
        "push {r1,r2,lr}\nmov r0,r10\nldrb r0,[r0]\nbl progression_allowed\npop {r1,r2}\nadd sp,#4\n"
        "cmp r0,#0\nbeq 1f\nldr r3,2f\nbx r3\n1:ldr r3,3f\nbx r3\n.balign 4\n2:.word 0x08093a83\n3:.word 0x08093a97");
}
__attribute__((naked,used)) void hook_equipment_edit(void){
    __asm__ volatile(
        "cmp r0,#0\nbne 1f\npush {r1,r2,lr}\nldr r0,[sp,#0x74]\nldrb r0,[r0]\n"
        "bl progression_allowed\npop {r1,r2}\nadd sp,#4\ncmp r0,#0\nbeq 1f\n"
        "ldr r3,2f\nbx r3\n1:ldr r3,3f\nbx r3\n.balign 4\n2:.word 0x080958f3\n3:.word 0x080958eb");
}
__attribute__((naked,used)) void hook_equipment_owner(void){
    __asm__ volatile(
        "push {r1,r2,lr}\nbl equipment_owner_allowed\npop {r1,r2}\nadd sp,#4\n"
        "cmp r0,#0\nbeq 1f\nldr r3,2f\nbx r3\n1:ldr r3,3f\nbx r3\n.balign 4\n2:.word 0x08095c9b\n3:.word 0x08095cb5");
}
/* Script opcode 0x23 contains story IDs, whereas the team API takes actual IDs. */
__attribute__((naked,used)) void hook_team_script(void){
    __asm__ volatile(
        "push {r2,lr}\nldrb r0,[r7,#2]\nbl story_actor\nmov r1,r0\nldrb r0,[r7,#1]\nldr r3,1f\nbl call_team\npop {r2}\nadd sp,#4\nldr r3,2f\nbx r3\ncall_team:bx r3\n.balign 4\n1:.word 0x08097579\n2:.word 0x08097e2b");
}

/* Used by the native scroll pickup parser, before its availability checks. */
unsigned remap_scroll(unsigned cid){return inverse_role(cid);}

__attribute__((naked,used)) u32 native_init(void){
    __asm__ volatile("push {r4,lr}\nsub sp,#4\nmovs r0,#0\nstr r0,[sp]\nldr r3,1f\nbx r3\n.balign 4\n1:.word 0x08068e05");
}
__attribute__((naked,used)) u32 native_add(u32 a,u32 b){
    __asm__ volatile("push {r4,r5,r6,r7,lr}\nmov r7,r10\nmov r6,r9\nmov r5,r8\nldr r3,1f\nbx r3\n.balign 4\n1:.word 0x0806d4a9");
}
__attribute__((naked,used)) u32 native_story(u32 a,u32 b,u32 c){
    __asm__ volatile("push {r4,r5,r6,r7,lr}\nmov r7,r10\nmov r6,r9\nmov r5,r8\nldr r3,1f\nbx r3\n.balign 4\n1:.word 0x0809761d");
}
__attribute__((naked,used)) u32 native_reward(u32 a,u32 b,void *window){
    __asm__ volatile("push {r4,r5,r6,r7,lr}\nmov r7,r9\nmov r6,r8\npush {r6,r7}\nldr r3,1f\nbx r3\n.balign 4\n1:.word 0x08097301");
}
__attribute__((naked,used)) u32 native_auto_skills(volatile u8 *a,u8 *b){
    __asm__ volatile("push {r4,r5,r6,r7,lr}\nmov r7,r8\npush {r7}\nmov r6,r0\nldr r3,1f\nbx r3\n.balign 4\n1:.word 0x080899f5");
}
__attribute__((naked,used)) u32 native_item_compatible(u32 a,u32 b){
    __asm__ volatile("push {r4,lr}\nlsl r0,r0,#24\nlsr r4,r0,#24\nlsl r1,r1,#24\nldr r3,1f\nbx r3\n.balign 4\n1:.word 0x0808fc29");
}

__attribute__((naked,used)) void hook_scroll(void){
    __asm__ volatile(
        "push {r7,lr}\nldrb r0,[r4,#1]\nbl remap_scroll\nmov r7,r0\n"
        "ldr r3,1f\nbl call_r3\ncmp r0,#0\nbne 5f\n"
        "movs r1,#1\nldr r2,2f\nmovs r3,#188\n"
        "3:mov r0,r1\nmul r0,r3\nadd r0,r2\nldrb r0,[r0,#4]\ncmp r0,r7\nbeq 4f\n"
        "add r1,#1\ncmp r1,#23\nbls 3b\nb 5f\n"
        "4:add r1,sp,#8\nstrh r7,[r1,#2]\nldrb r1,[r4,#2]\nldrb r2,[r4,#3]\nmovs r0,#4\nadd r3,sp,#8\nldr r7,6f\nbl call_r7\n"
        "5:pop {r7}\nadd sp,#4\nadd r5,r6,#1\nldr r3,7f\nbx r3\n"
        "call_r3:bx r3\ncall_r7:bx r7\n.balign 4\n"
        "1:.word 0x0806d659\n2:.word 0x02022e30\n6:.word 0x08081025\n7:.word 0x0806e947");
}
