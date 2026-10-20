#include <stdint.h>
typedef uint8_t u8;typedef uint32_t u32;
#define R8(a) (*(volatile u8*)(a))
#define R32(a) (*(volatile u32*)(a))

/* Flags belong to battle positions, never to a persistent party character. */
u32 campaign_is_invulnerable(const volatile u8 *actor){
 unsigned scene=R8(0x02026805),sub=R8(0x02026806);
 if(scene<56||scene>=104||sub>2||R8(0x02026807))return 0;
 const u8 *p=(const u8*)(CAMPAIGN_MODIFIERS+scene*6+sub*2);
 unsigned mask=p[0]|p[1]<<8;
 for(unsigned n=1;n<=12;n++)if(actor==(const volatile u8*)(0x020240c0+n*468))return actor[204]&&!!(mask&(1u<<(n-1)));
 return 0;
}
u32 campaign_guard_damage(const volatile u8 *actor,u32 damage){return campaign_is_invulnerable(actor)?0:damage;}
extern u32 campaign_native_remove(u32,u32,u32);
u32 campaign_remove(u32 victim,u32 source,u32 mode){
 volatile u8 *a=(volatile u8*)(0x020240c0+victim*468);
 if(victim>=1&&victim<=12&&campaign_is_invulnerable(a)){
  a[12]=a[14];a[13]=a[15];return 0;
 }
 return campaign_native_remove(victim,source,mode);
}
void campaign_protection_setup(void){
 for(unsigned n=1;n<=12;n++){
  volatile u8 *a=(volatile u8*)(0x020240c0+n*468);
  if(!a[0]||!campaign_is_invulnerable(a))continue;
  a[2]=99;a[3]=99;a[4]=99;a[14]=999&255;a[15]=999>>8;a[12]=a[14];a[13]=a[15];
 }
}
u32 campaign_arrived(const u8 *rule){
 unsigned cid=rule[1];
 if(cid>=1&&cid<=21&&R32(0x02022ea0)==0x33544b4e)cid=R8(0x02022ea4+cid-1);
 for(unsigned n=1;n<=12;n++){
  volatile u8 *a=(volatile u8*)(0x020240c0+n*468);
  if(a[0]==cid&&!a[204]&&(a[12]||a[13])&&a[196]==rule[2]&&a[197]==rule[3]&&(a[192]&16))return 1;
 }
 return 0;
}
