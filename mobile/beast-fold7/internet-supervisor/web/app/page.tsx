import {redirect} from 'next/navigation';
import {ownerSession} from '../lib/auth';
import Dashboard from './ui/dashboard';
export const dynamic='force-dynamic';
export default async function Page(){const session=await ownerSession();if(!session)redirect('/login');return <Dashboard/>;}
