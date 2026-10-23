import { StockPage } from '@/components/stock-page';
export default async function Page({params}:{params:Promise<{symbol:string}>}){const {symbol}=await params;return <StockPage symbol={decodeURIComponent(symbol).toUpperCase()}/>;}
