import Dashboard from './dashboard';
import {getChatGPTUser} from './chatgpt-auth';
export const dynamic='force-dynamic';
export default async function Home() {const user=await getChatGPTUser();return <Dashboard signedIn={!!user} />;}
