import {env} from 'cloudflare:workers';
export function database(){if(!env.DB)throw new Error('Storage is unavailable. Please retry after setup is complete.');return env.DB;}
export function providerKey(){return (env as unknown as Record<string,unknown>).ODDS_API_KEY as string|undefined;}
