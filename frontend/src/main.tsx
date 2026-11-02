import React,{useEffect,useState} from 'react';
import{createRoot}from'react-dom/client';
import ReactFlow,{Background,Controls,type Node,type Edge}from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import ReactECharts from 'echarts-for-react';
import './style.css';
const API='http://127.0.0.1:8000';
type Chat={id:string;title:string};
type Msg={id:string;role:string;content:string};
type Memory={id:string;subject:string;predicate:string;object:string;status:string;message_id:string};
async function request(path:string,options?:RequestInit){const r=await fetch(API+path,options);if(!r.ok)throw Error((await r.text()).slice(0,200));return r.json();}
const post=(path:string,body:unknown)=>request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function App(){
const[page,setPage]=useState('Обзор'),[chats,setChats]=useState<Chat[]>([]),[chat,setChat]=useState(''),[messages,setMessages]=useState<Msg[]>([]),[memories,setMemories]=useState<Memory[]>([]),[graph,setGraph]=useState<{nodes:Node[];edges:Edge[]}>({nodes:[],edges:[]}),[stats,setStats]=useState({chats:0,messages:0,memories:0}),[prompt,setPrompt]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[search,setSearch]=useState(''),[results,setResults]=useState<Msg[]>([]);
async function refresh(){try{const[c,s,m,g]=await Promise.all([request('/api/chats'),request('/api/stats'),request('/api/memories'),request('/api/graph')]);setChats(c);setStats(s);setMemories(m);setGraph({nodes:g.nodes.map((n:{id:string;label:string},i:number)=>({id:n.id,data:{label:n.label},position:{x:(i%6)*190,y:Math.floor(i/6)*110}})),edges:g.edges.map((e:{id:string;source:string;target:string;label:string})=>({...e,label:e.label}))});}catch(e){setError(String(e));}}
useEffect(()=>{refresh()},[]);
useEffect(()=>{if(chat)request('/api/chats/'+chat+'/messages').then(setMessages).catch(e=>setError(String(e)))},[chat]);
async function newChat(){try{const c=await post('/api/chats',{title:'Новый разговор'});await refresh();setChat(c.id);setPage('Чаты')}catch(e){setError(String(e))}}
async function send(){if(!prompt.trim()||busy)return;setBusy(true);setError('');try{let id=chat;if(!id){const c=await post('/api/chats',{title:prompt.slice(0,60)});id=c.id;setChat(id)}const p=prompt;setPrompt('');const result=await post('/api/ask',{chat_id:id,prompt:p});setMessages(await request('/api/chats/'+id+'/messages'));await refresh();if(!result.answer)setError('Empty response')}catch(e){setError(String(e))}finally{setBusy(false)}}
async function find(){try{setResults(await request('/api/search?q='+encodeURIComponent(search)))}catch(e){setError(String(e))}}
const menu=['Обзор','Чаты','Память','Граф знаний','Поиск','Развитие','Документы','Агенты','Автоматизация','Подключения','Настройки'];
return <div className="layout"><aside><div className="brand">✦ AION <span>MEMORY</span></div><div className="small">Интеллектуальная память · v0.1.0</div><nav>{menu.map(m=><button key={m} className={page===m?'active':''} onClick={()=>setPage(m)}>{m}</button>)}</nav><div className="asidefoot">Локальный архив · без Docker</div></aside><main><header><div><h1>{page}</h1><p>Единое пространство памяти и знаний</p></div><button className="primary" onClick={newChat}>+ Новый чат</button></header>{error&&<div className="error" role="alert">{error}<button onClick={()=>setError('')}>×</button></div>}
{page==='Обзор'&&<><section className="cards">{Object.entries(stats).map(([k,v])=><article key={k}><span>{({chats:'Чаты',messages:'Сообщения',memories:'Факты'} as Record<string,string>)[k]}</span><strong>{v}</strong></article>)}</section><section className="panel"><h2>Активность памяти</h2><ReactECharts option={{xAxis:{type:'category',data:['Чаты','Сообщения','Факты']},yAxis:{type:'value'},series:[{type:'bar',data:[stats.chats,stats.messages,stats.memories],itemStyle:{color:'#b99150'}}]}} style={{height:290}}/></section></>}
{page==='Чаты'&&<div className="split"><section className="panel chatlist"><h2>История</h2>{chats.map(c=><button key={c.id} className={chat===c.id?'selected':''} onClick={()=>setChat(c.id)}>{c.title}</button>)}</section><section className="panel chat"><div className="messages">{messages.map(m=><div className={'bubble '+m.role} key={m.id}><small>{m.role}</small><div>{m.content}</div></div>)}</div><div className="composer"><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder="Напишите сообщение..." onKeyDown={e=>{if(e.key==='Enter'&&e.ctrlKey)send()}}/><button className="primary" disabled={busy} onClick={send}>{busy?'Ожидание...':'Отправить'}</button></div></section></div>}
{page==='Память'&&<section className="panel"><h2>Извлечённые знания</h2><p>Ручная регистрация фактов через API; автоматическое извлечение запланировано. Неподтверждённые факты не передаются модели.</p>{memories.map(m=><div className="fact" key={m.id}><b>{m.subject}</b> — {m.predicate} → {m.object}<small> {m.status} · источник {m.message_id}</small></div>)}</section>}
{page==='Граф знаний'&&<section className="panel"><h2>Карта знаний</h2><div style={{height:'65vh'}}><ReactFlow nodes={graph.nodes} edges={graph.edges} fitView><Background/><Controls/></ReactFlow></div></section>}
{page==='Поиск'&&<section className="panel"><h2>Поиск по полному архиву</h2><div className="search"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Поиск сообщений"/><button onClick={find}>Найти</button></div>{results.map(m=><div className="fact" key={m.id}>{m.content}</div>)}</section>}
{!['Обзор','Чаты','Память','Граф знаний','Поиск'].includes(page)&&<section className="panel"><h2>{page}</h2><p>Раздел подготовлен в навигации. Интеграция ещё не реализована. Для подключения Cloud.ru укажите параметры в локальном файле .env; ключи никогда не помещайте в репозиторий.</p></section>}
</main></div>}
createRoot(document.getElementById('root')!).render(<App/>);
