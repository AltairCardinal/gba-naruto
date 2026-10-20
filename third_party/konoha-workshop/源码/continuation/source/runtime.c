#include <stdint.h>
typedef uint8_t u8;typedef uint32_t u32;
#define R8(a) (*(volatile u8*)(a))
#define R32(a) (*(volatile u32*)(a))
extern u32 campaign_native_battle_init(void);
extern void campaign_protection_setup(void);
extern u32 campaign_is_invulnerable(const volatile u8*);
static unsigned campaign_party_level(void){unsigned level=12;for(unsigned n=1;n<=23;n++){volatile u8 *a=(volatile u8*)(0x02022e34+n*188);if(a[0]&&a[1]>level)level=a[1];}return level>50?50:level;}
static void campaign_unlock_position(volatile u8 *a,unsigned role){
 /* The new campaign starts after Haku and the curse-mark incident. */
 if(role<1||role>3)return;
 for(unsigned i=0;i<24;i++)if(a[0x50+i*4]>23&&a[0x50+i*4]<255&&a[0x51+i*4]==255)a[0x51+i*4]=1;
}
void campaign_prepare(void){
 const u32 *original=(const u32*)0x08599280;volatile u32 *names=(volatile u32*)0x0203e800;
 unsigned scene=R8(0x020311ea);for(unsigned id=0;id<64;id++)names[id]=original[id];
 const u32 *skills=(const u32*)0x08545458;volatile u32 *skillRam=(volatile u32*)0x0203e900;
 for(unsigned i=0;i<348;i++)skillRam[i]=skills[i];
 if(scene>=56&&scene<104)R8(0x0203e900+5*16+4)=CAMPAIGN_BASIC_ATTACK;
 if(scene>=56&&scene<104){const u32 *custom=(const u32*)(CAMPAIGN_NAME_MAP+scene*64*4);for(unsigned id=0;id<64;id++)if(custom[id])names[id]=custom[id];}
}
/* Native new-game init leaves the previous story branch and battle result intact. */
extern u32 campaign_original_new_game(void);
u32 campaign_new_game(void){
 u32 result=campaign_original_new_game();
 R8(0x020311ec)=0; /* before-story branch, including warm starts after defeat */
 R8(0x020311ed)=0; /* configuration */
 R8(0x020311ee)=0;
 R8(0x020311ef)=0;
 R8(0x02026807)=0; /* previous battle outcome */
 campaign_prepare();
 return result;
}
extern u32 campaign_native_storage_io(u32,u32);
u32 campaign_storage_io(u32 operation,u32 slot){u32 result=campaign_native_storage_io(operation,slot);campaign_prepare();return result;}
extern u32 campaign_native_load(u32);
extern u32 campaign_native_suspend_load(void);
u32 campaign_load(u32 slot){u32 result=campaign_native_load(slot);campaign_prepare();return result;}
u32 campaign_suspend_load(void){u32 result=campaign_native_suspend_load();campaign_prepare();return result;}
u32 campaign_battle_init(void){
 campaign_prepare();
 unsigned scene=R8(0x02026805);if(scene>=56&&scene<104)R8(0x0203150f)&=127;
 if(scene>=56&&scene<104){
  const u8 *loadouts=(const u8*)(CAMPAIGN_LOADOUTS+(scene-56)*12*32);
  const u8 *presets=(const u8*)(CAMPAIGN_ACTORS+scene*0x1aac+R8(0x02026806)*0x8e4+4);
  for(unsigned slot=0;slot<12;slot++){
   const u8 *preset=presets+slot*0xb8,*load=loadouts+slot*32;unsigned id=preset[0];
   if(!id||preset[1]||!load[0])continue;
   if(id<=21&&R32(0x02022ea0)==0x33544b4e){unsigned actual=R8(0x02022ea4+id-1);if(actual!=id)continue;id=actual;}
   for(unsigned n=1;n<=23;n++){
    volatile u8 *actor=(volatile u8*)(0x02022e34+n*188);if(actor[0]!=id)continue;
    /* Keep earned ranks and usage progress for skills present in this scene. */
    u32 known[15];for(unsigned i=0;i<15;i++)known[i]=((volatile u32*)(actor+0x14))[i];
    for(unsigned i=0;i<15;i++){
     unsigned skill=load[1+i*2],rank=load[2+i*2];u32 value=skill|(rank<<8);
     if(skill)for(unsigned j=0;j<15;j++){unsigned oldrank=(known[j]>>8)&255;if((known[j]&255)==skill&&oldrank&&oldrank<255){value=known[j];if(oldrank<rank)value=(value&~0xff00u)|(rank<<8);break;}}
     ((volatile u32*)(actor+0x14))[i]=value;
    }
   }
  }
 }
 u32 result=campaign_native_battle_init();
 if(!CAMPAIGN_RESTART&&scene>=56&&scene<104){
  unsigned floor=12,scaled=(scene-56)*55,party=campaign_party_level();while(scaled>=100){scaled-=100;floor++;}
  if(party>floor)for(unsigned n=1;n<=12;n++){
   volatile u8 *a=(volatile u8*)(0x020240c0+n*468);if(!a[0]||!a[204]||campaign_is_invulnerable(a))continue;
   unsigned level=a[1]+party-floor;a[1]=level>50?50:level;
   ((void(*)(void*,u32,u32))0x0806d965)((void*)a,0,0);
   unsigned hp=a[14]|a[15]<<8,ceiling=60+a[1]*8;if(hp>ceiling){a[14]=ceiling;a[15]=ceiling>>8;}a[12]=a[14];a[13]=a[15];
  }
 }
 if(scene>=56&&scene<104)for(unsigned n=1;n<=12;n++){
  volatile u8 *a=(volatile u8*)(0x020240c0+n*468);if(!a[0]||a[204])continue;
  unsigned bonus=CAMPAIGN_RESTART?8:4;
  for(unsigned j=2;j<=4;j++){unsigned v=a[j]+bonus;a[j]=v>99?99:v;}
  unsigned hp=a[14]|a[15]<<8,min=CAMPAIGN_RESTART?120+a[1]*10:120,preset=R8(CAMPAIGN_LOADOUTS+(scene-56)*384+(n-1)*32+31)*10;
  if(min<preset)min=preset;
  if(hp<min){hp=min;if(hp>999)hp=999;a[14]=hp;a[15]=hp>>8;}a[12]=a[14];a[13]=a[15];
 }
 campaign_protection_setup();
 return result;
}

u32 campaign_progression_allowed(u32 cid){
 unsigned scene=R8(0x020311ea);
 if(scene>=56&&scene<104)return 1;
 if(((u32(*)(void))0x08097131)())return 1;
 if(R32(0x02022ea0)==0x33544b4e)return cid==R8(0x02022ea4)||cid==R8(0x02022ea5)||cid==R8(0x02022ea6);
 return cid>=1&&cid<=3;
}

u32 campaign_story(u32 action,u32 cid,u32 level){
 unsigned scene=R8(0x020311ea),actual=cid;
 if(scene>=56&&scene<104&&action){
  if(!CAMPAIGN_RESTART){unsigned trained=campaign_party_level();if(level<trained)level=trained;}
  if(cid>=1&&cid<=21&&R32(0x02022ea0)==0x33544b4e)actual=R8(0x02022ea4+cid-1);
  for(unsigned n=1;n<=23;n++)if(R8(0x02022e34+n*188)==actual){volatile u8 *a=(volatile u8*)(0x02022e34+n*188);campaign_unlock_position(a,cid);if(a[1]<level){a[1]=level;((void(*)(void*,u32,u32))0x0806d965)((void*)a,0,0);}a[12]=a[14];a[13]=a[15];((void(*)(u32,u32))0x08097579)(1,actual);return 1;}
 }
 u32 result=((u32(*)(u32,u32,u32))OLD_STORY)(action,cid,level);
 if(scene>=56&&scene<104&&action)for(unsigned n=1;n<=23;n++){
  volatile u8 *a=(volatile u8*)(0x02022e34+n*188);if(a[0]!=actual)continue;
  campaign_unlock_position(a,cid);
  if(a[1]<level){a[1]=level;((void(*)(void*,u32,u32))0x0806d965)((void*)a,0,0);}a[12]=a[14];a[13]=a[15];break;
 }
 return result;
}
extern u32 campaign_native_stats(void*,void*,void*);
u32 campaign_stats(volatile u8 *actor,void *a,void *b){
 unsigned scene=R8(0x020311ea),old=actor[0];
 if(scene>=56&&scene<104&&old<64){unsigned profile=R8(CAMPAIGN_PROFILES+scene*64+old);if(profile)actor[0]=profile;}
 u32 result=campaign_native_stats((void*)actor,a,b);actor[0]=old;
 if(scene>=56&&scene<104){
  const u8 *presets=(const u8*)(CAMPAIGN_ACTORS+scene*0x1aac+R8(0x02026806)*0x8e4+4);
  for(unsigned n=0;n<12;n++)if(presets[n*0xb8]==old&&!presets[n*0xb8+1]){
   unsigned floor=R8(CAMPAIGN_LOADOUTS+(scene-56)*384+n*32+31)*10,hp=actor[14]|actor[15]<<8;
   if(!CAMPAIGN_RESTART&&floor<hp+(hp>>2))floor=hp+(hp>>2);
   if(hp<floor){if(floor>999)floor=999;actor[14]=floor;actor[15]=floor>>8;}break;
  }
 }
 return result;
}
void campaign_entry(void){
 unsigned progress=R8(0x020311e4)|(R8(0x020311e5)<<8);
 /* A completed original save enters the continuation once, with its party intact. */
 if(R8(0x020311ea)==54&&progress==370){R8(0x020311ea)=56;R8(0x020311ec)=0;R8(0x020311e4)=0x80;R8(0x020311e5)=1;}
 unsigned scene=R8(0x020311ea);if(scene>=56&&scene<104)R8(0x0203150f)&=127;else if(scene==54&&progress==385)R8(0x0203150f)|=128;
 campaign_prepare();
}
