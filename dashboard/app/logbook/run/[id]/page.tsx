import { EventFeed } from '@/components/event-feed';
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <EventFeed full runId={id}/>;}
