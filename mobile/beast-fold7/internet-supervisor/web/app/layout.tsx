import type {ReactNode} from 'react';
import './globals.css';
import './supervisor.css';
import AutoScrollbar from './ui/auto-scrollbar';
export const metadata={title:'AR Assembly | 관제',description:'조립 작업 관제'};
export default function Layout({children}:{children:ReactNode}){
  return <html lang="ko" data-theme="dark"><head><link rel="stylesheet" href="/base.css"/><link rel="stylesheet" href="/observer.css"/></head><body><AutoScrollbar/>{children}</body></html>;
}
