'use client';
import {useEffect} from 'react';

export default function AutoScrollbar(){
  useEffect(()=>{
    const root=document.documentElement;
    let timer:ReturnType<typeof setTimeout>,edge=false,keyboard=false;
    root.dataset.autoScrollbar='true';
    function reveal(){
      clearTimeout(timer);root.dataset.scrollbarVisible='true';
      if(!edge&&!keyboard)timer=setTimeout(()=>{root.dataset.scrollbarVisible='false';},1500);
    }
    function move(e:PointerEvent){
      const near=e.clientX>=root.clientWidth-20;
      if(near!==edge){edge=near;reveal();}
    }
    function leave(){edge=false;reveal();}
    function key(e:KeyboardEvent){if(['Tab','ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(e.key)){keyboard=true;reveal();}}
    function pointer(){keyboard=false;reveal();}
    window.addEventListener('scroll',reveal,true);
    window.addEventListener('pointermove',move,{passive:true});
    window.addEventListener('pointerdown',pointer,{passive:true});
    document.addEventListener('pointerleave',leave);
    window.addEventListener('keydown',key);
    reveal();
    return()=>{clearTimeout(timer);window.removeEventListener('scroll',reveal,true);window.removeEventListener('pointermove',move);window.removeEventListener('pointerdown',pointer);document.removeEventListener('pointerleave',leave);window.removeEventListener('keydown',key);delete root.dataset.autoScrollbar;delete root.dataset.scrollbarVisible;};
  },[]);
  return null;
}
