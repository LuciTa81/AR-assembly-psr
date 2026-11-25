import {Box,LockKeyhole} from 'lucide-react';
import {authConfigured} from '../../lib/auth';
import LoginButton from '../ui/login-button';
export const dynamic='force-dynamic';
export default async function Login({searchParams}:{searchParams:Promise<{error?:string}>}){
  const {error}=await searchParams;
  return <main className="login-layout assembly-login" data-theme="dark">
    <div className="assembly-backdrop" aria-hidden="true"/>
    <div className="login-center"><a className="brand" href="/"><Box className="icon brand-icon"/><span>AR Assembly<small>조립 작업 관제</small></span></a>
    <section className="login-form" aria-labelledby="login-title"><div className="login-title-row"><h1 id="login-title">관제 로그인</h1><LockKeyhole size={20} aria-hidden="true"/></div><p>내 기기와 작업 기록을 한곳에서.</p>
    {error&&<p role="alert" className="warning">로그인할 수 없어요. 허용된 GitHub 계정인지 확인해 주세요.</p>}
    <LoginButton configured={authConfigured()}/></section><span className="login-caption">AR ASSEMBLY · WORKSPACE</span></div></main>;
}
