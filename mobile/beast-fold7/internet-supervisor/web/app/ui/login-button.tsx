'use client';
import {signIn} from 'next-auth/react';
import {LogIn} from 'lucide-react';
export default function LoginButton({configured}:{configured:boolean}){
  return <><button className="primary-button" disabled={!configured} onClick={()=>void signIn('github',{callbackUrl:'/'})}><LogIn size={20}/>GitHub로 로그인</button>
    {!configured&&<p role="status" className="warning">로그인 연결을 준비하고 있어요.</p>}</>;
}
