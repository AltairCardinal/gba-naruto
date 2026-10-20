'use strict';
(()=>{
const $=s=>document.querySelector(s),data=window.DEMO_DATA;
$('#expected').textContent='原输入 SHA256：'+data.source_sha256;
const crcTable=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;crcTable[n]=c>>>0;}
const crc=b=>{let c=0xffffffff;for(let i=0;i<b.length;i++)c=crcTable[(c^b[i])&255]^(c>>>8);return(c^0xffffffff)>>>0;};
const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b)),x=>x.toString(16).padStart(2,'0')).join('');
function apply(source,patch){
 if(String.fromCharCode(...patch.subarray(0,4))!=='BPS1')throw Error('补丁格式不正确');
 const view=new DataView(patch.buffer,patch.byteOffset,patch.byteLength),tail=patch.length-12;
 if(crc(patch.subarray(0,-4))!==view.getUint32(patch.length-4,true))throw Error('补丁校验失败');
 let at=4;const num=()=>{let val=0,shift=1;for(let k=0;k<8;k++){if(at>=tail)throw Error('补丁提前结束');let b=patch[at++];val+=(b&127)*shift;if(b&128)return val;shift*=128;val+=shift;}throw Error('补丁整数过长');};
 const sourceSize=num(),targetSize=num(),metadata=num();at+=metadata;
 if(sourceSize!==source.length||crc(source)!==view.getUint32(tail,true))throw Error('原输入校验失败');
 if(targetSize>16*1024*1024||at>tail)throw Error('补丁大小不正确');
 const out=new Uint8Array(targetSize);let pos=0;
 while(pos<targetSize){const action=num(),length=Math.floor(action/4)+1,kind=action&3;if(pos+length>targetSize)throw Error('补丁越界');
  if(kind===0){if(pos+length>source.length)throw Error('原输入越界');out.set(source.subarray(pos,pos+length),pos);}
  else if(kind===1){if(at+length>tail)throw Error('补丁数据越界');out.set(patch.subarray(at,at+length),pos);at+=length;}
  else throw Error('本包补丁含不支持的指令');pos+=length;
 }
 if(at!==tail||crc(out)!==view.getUint32(tail+4,true))throw Error('生成结果校验失败');return out;
}
window.applyDemoPatch=apply;
$('#generate').onclick=async()=>{
 const button=$('#generate'),status=$('#status'),file=$('#sourceFile').files[0];
 if(!file){status.textContent='请先选择自己准备的对应原版文件。';return;}
 button.disabled=true;try{
  if(file.size>16*1024*1024)throw Error('文件超过16MB，请选择对应GBA原版');
  status.textContent='正在核对原输入……';const source=new Uint8Array(await file.arrayBuffer());if(await sha(source)!==data.source_sha256)throw Error('原输入不匹配。请核对文件名称与SHA256，不要选择其他改版。');
  const target=data.patches[$('#edition').value],patch=Uint8Array.from(atob(target.base64),c=>c.charCodeAt(0));status.textContent='正在应用'+target.label+'补丁……';
  const out=apply(source,patch);if(await sha(out)!==target.target_sha256)throw Error('生成结果SHA256不匹配');
  const url=URL.createObjectURL(new Blob([out],{type:'application/octet-stream'})),a=document.createElement('a');a.href=url;a.download=target.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
  status.textContent='生成成功：'+target.filename+'\n请保存浏览器下载，然后打开编辑器选择它。\nSHA256：'+target.target_sha256;
 }catch(e){status.textContent='未生成：'+e.message;}finally{button.disabled=false;}
};
})();
