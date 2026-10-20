/* Record native GBA audio from a cold-booted, temporary preview ROM. */
#include <mgba/flags.h>
#include <mgba/core/core.h>
#include <mgba/core/config.h>
#include <mgba/core/log.h>
#include <mgba-util/audio-buffer.h>
#include <stdio.h>
#include <stdlib.h>
static void quiet(struct mLogger*l,int category,enum mLogLevel level,const char*fmt,va_list args){}
static void frames(struct mCore*c,unsigned n,unsigned keys){c->setKeys(c,keys);for(unsigned i=0;i<n;i++){c->runFrame(c);mAudioBufferClear(c->getAudioBuffer(c));}c->setKeys(c,0);}
static void key(struct mCore*c,unsigned k,unsigned wait){frames(c,8,k);frames(c,12+wait,0);}
int main(int argc,char**argv){if(argc!=3)return 2;struct mLogger logger={.log=quiet,.filter=NULL};mLogSetDefaultLogger(&logger);struct mCore*c=mCoreFind(argv[1]);if(!c||!c->init(c))return 3;mCoreInitConfig(c,"naruto-music-preview");mCoreConfigSetDefaultIntValue(&c->config,"volume",256);mCoreLoadConfig(c);mColor*p=calloc(256*256,sizeof(mColor));c->setVideoBuffer(c,p,256);c->setAudioBufferSize(c,4096);if(!mCoreLoadFile(c,argv[1]))return 4;c->reset(c);fprintf(stderr,"VOL %d MUTE %d\n",c->opts.volume,c->opts.mute);frames(c,950,0);if(getenv("PREVIEW_TITLE")){}else if(getenv("PREVIEW_ORIGINAL")){key(c,8,100);key(c,1,40);frames(c,10,0);}else{key(c,8,100);key(c,1,180);key(c,8,250);frames(c,80,0);}fprintf(stderr,"SOUNDREG %04x %04x %04x\n",c->busRead16(c,0x04000080),c->busRead16(c,0x04000082),c->busRead16(c,0x04000084));FILE*f=fopen(argv[2],"wb");if(!f)return 5;int16_t samples[8192];size_t total=0;for(int i=0;i<900;i++){c->runFrame(c);size_t n=mAudioBufferRead(c->getAudioBuffer(c),samples,4096);fwrite(samples,4,n,f);total+=n;}fclose(f);printf("RATE %u SAMPLES %zu SCENE %u BRANCH %u\n",c->audioSampleRate(c),total,c->busRead8(c,0x020311ea),c->busRead8(c,0x020311ec));c->deinit(c);free(p);return 0;}
