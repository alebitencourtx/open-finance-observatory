"use strict";
(() => {
  const D = window.OFB_DATA;
  const $ = s => document.querySelector(s);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  if (!D) { $("#view").innerHTML = '<div class="empty">Base indisponível. Execute <strong>observatory build</strong> e recarregue a página.</div>'; return; }
  const fmt = (v, digits=0) => v == null ? "—" : Number(v).toLocaleString("pt-BR", {minimumFractionDigits:digits,maximumFractionDigits:digits});
  const pct = (v, digits=1) => v == null ? "—" : `${fmt(v,digits)}%`;
  const colors = {santander:"#cd5867",itau:"#dc963e",bradesco:"#617ca6"};
  const short = {santander:"Santander",itau:"Itaú Unibanco",bradesco:"Bradesco"};
  const familyColors = {"Investimentos":"#287f75","Cartões":"#6db2a6"};
  const icons = {
    overview:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    coverage:'<path d="M4 4h16v16H4zM4 9h16M4 14h16M9 4v16M15 4v16"/>',
    portfolio:'<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V4h8v3M3 12h18M10 12v3h4v-3"/>',
    rates:'<path d="M4 20V4M4 20h17M7 15l4-5 4 2 5-7"/><path d="M16 5h4v4"/>',
    channels:'<path d="M19 10c0 6-7 11-7 11S5 16 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
    quality:'<path d="m12 3 8 3v6c0 4-8 9-8 9s-8-5-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    methodology:'<path d="M4 3h12l4 4v14H4zM15 3v5h5M8 12h8M8 16h6"/>',
    endpoint:'<path d="M8 7H5a3 3 0 0 0-3 3v4a3 3 0 0 0 3 3h3M16 7h3a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3h-3M8 12h8"/>'
  };
  const icon = (name, cls="nav-icon") => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.overview}</svg>`;
  const views = {
    overview:["Visão executiva","Panorama competitivo","Uma leitura integrada da presença e da qualidade de publicação do mercado."],
    coverage:["Cobertura de APIs","Amplitude de publicação","O que cada conglomerado declara e o que está efetivamente disponível."],
    portfolio:["Portfólio de produtos","A dimensão de cada oferta","Explore as ofertas publicadas, os segmentos atendidos e suas fontes."],
    rates:["Taxas e tarifas","Preços sob a mesma régua","Distribuições de taxas mínimas publicadas, com unidade e amostra explícitas."],
    channels:["Rede de atendimento","Presença que se materializa","Compare a composição da rede e sua distribuição no território brasileiro."],
    exchange:["Câmbio e VET","Condições de câmbio publicadas","Cotações online e distribuições de VET preservadas por operação e moeda."],
    quality:["Qualidade dos dados","Confiança em cada evidência","Completude, disponibilidade de dados e consistência das publicações."],
    methodology:["Metodologia e fontes","Critérios que sustentam a leitura","Definições, limites e rastreabilidade para uma análise reproduzível."]
  };
  const state = {view:"overview",groups:new Set(D.group_metrics.map(g=>g.group_id)),family:"Todas",segment:"Todos",search:"",page:0,sort:"name",direction:1,rateType:"",feeService:"Todos",rateFamily:"Empréstimos",rateSegment:"PF",rateUnit:"pct_month",rateIndexer:"PRE_FIXADO",uf:"Todas",incident:"Todos"};
  const chosen = () => D.group_metrics.filter(g=>state.groups.has(g.group_id));
  const selected = rows => rows.filter(r=>state.groups.has(r.group_id));
  const sum = (rows,key) => rows.reduce((n,r)=>n+(Number(r[key])||0),0);
  const institution = id => `<span class="institution"><span class="dot" style="background:${colors[id] || '#758b97'}"></span>${esc(short[id]||id)}</span>`;
  const date = (value, options) => new Date(value).toLocaleDateString("pt-BR",options || {day:"2-digit",month:"short",year:"numeric",timeZone:"America/Sao_Paulo"});
  const dateTime = value => new Date(value).toLocaleString("pt-BR",{timeZone:"America/Sao_Paulo"});
  const badge = (label,kind="") => `<span class="badge ${kind}">${esc(label)}</span>`;
  const panel = (title,sub,body,action="",classes="") => `<section class="panel ${classes}"><div class="panel-header"><div><h2>${title}</h2><p class="panel-subtitle">${sub}</p></div>${action}</div><div class="panel-content">${body}</div></section>`;
  const link = (view,text) => `<button class="text-link" data-view="${view}">${text} <span>↗</span></button>`;
  const metric = (label,value,unit,note,iconName,percent=100,warn=false) => `<article class="metric-card"><div class="metric-top">${label}${icon(iconName,"metric-icon")}</div><div class="metric-number">${value}<span class="metric-unit">${unit}</span></div><div class="metric-note ${warn?'amber':''}">${note}</div><div class="metric-rule ${warn?'amber':''}"><span style="width:${Math.min(100,Math.max(0,percent))}%"></span></div></article>`;
  const empty = text => `<div class="empty">${esc(text)}</div>`;
  const options = (values,current) => values.map(v=>`<option value="${esc(v)}" ${v===current?'selected':''}>${esc(v)}</option>`).join("");
  const indexerLabel = value => ({FLUTUANTES_CDI:'CDI',FLUTUANTES_SELIC:'Selic',POS_FIXADO_TR_TBF:'TR / TBF',POS_FIXADO_TJLP:'TJLP',POS_FIXADO_TLP:'TLP',INDICES_PRECOS_IPCA:'IPCA',INDICES_PRECOS_IGPM:'IGP-M'}[value] || value);

  function heatmap(full=false) {
    const gs=chosen();
    let families=D.families;
    if(!full) families = ["Contas","Cartões","Empréstimos","Financiamentos","Investimentos","Seguros","Canais","Métricas"];
    return `<table class="heatmap ${full?'full-heatmap':''}"><thead><tr><th>Família de APIs</th>${gs.map(g=>`<th>${institution(g.group_id)}</th>`).join("")}</tr></thead><tbody>${families.map(f=>`<tr><th scope="row">${esc(f)}</th>${gs.map(g=>{
      const c=D.coverage.find(r=>r.group_id===g.group_id&&r.family_label===f);
      const cls=c?.published?'':c?.declared?'empty':'undeclared';
      const label=c?.published?(full?`${fmt(c.records)} registros`:'Publicado'):c?.declared?(full?'Sem dados':'—'):(full?'Não declarado':'n/d');
      return `<td><button class="heat-cell ${cls}" data-coverage="${esc(f)}" data-group="${g.group_id}" aria-label="${esc(g.label)}, ${esc(f)}: ${label}">${full?label:c?.published?'✓':c?.declared?'—':'n/d'}</button></td>`;
    }).join("")}</tr>`).join("")}</tbody></table><div class="legend heatmap-legend"><span class="legend-item"><span class="legend-square" style="background:#b4dfcf"></span>Com dados</span><span class="legend-item"><span class="legend-square" style="background:#f1d49f"></span>Declarado, sem dados</span><span class="legend-item"><span class="legend-square" style="background:#dfe5e9"></span>Não declarado</span></div>`;
  }

  function overview() {
    const gs=chosen(), endpoints=sum(gs,"endpoints"), products=sum(gs,"products"), physical=sum(gs,"physical_channels"), complete=sum(gs,"complete"), attention=endpoints-complete;
    const best=[...gs].sort((a,b)=>b.quality_score-a.quality_score)[0];
    const worst=[...gs].sort((a,b)=>a.quality_score-b.quality_score)[0];
    const success=endpoints?100*complete/endpoints:0;
    const catalogTop=[...gs].sort((a,b)=>b.products-a.products)[0];
    const topProducts=Math.max(...gs.map(g=>g.products),1);
    const records=sum(gs,"raw_records");
    const rank = `<div class="legend">${gs.map(g=>`<span class="legend-item"><span class="dot" style="background:${colors[g.group_id]}"></span>${esc(g.group_id==='itau'?'Itaú':g.label)}</span>`).join("")}</div><div class="score-rows">${[...gs].sort((a,b)=>b.quality_score-a.quality_score).map(g=>`<div class="score-row"><span>${institution(g.group_id)}</span><div class="score-track"><div class="score-bar" style="width:${g.quality_score||0}%;background:${colors[g.group_id]}"></div></div><span class="score-value">${fmt(g.quality_score,1)}</span></div>`).join("")}</div><div class="chart-axis"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div><div class="chart-foot"><span>Índice técnico · média dos componentes disponíveis</span>${link('quality','Ver componentes')}</div>`;
    const portfolio = `<div class="portfolio-rows">${gs.map(g=>{
      const fam = Object.entries(D.products_family.filter(r=>r.group_id===g.group_id).reduce((a,r)=>{a[r.family_label]=(a[r.family_label]||0)+r.count;return a;},{})).map(([family_label,count])=>({family_label,count}));
      return `<div><div class="portfolio-line">${institution(g.group_id)}<strong>${fmt(g.products)}</strong></div><div class="stacked-track" style="width:${Math.max(2,100*g.products/topProducts)}%" aria-label="${esc(g.label)}: ${fmt(g.products)} ofertas">${fam.map(r=>`<span title="${esc(r.family_label)}: ${fmt(r.count)}" style="width:${100*r.count/Math.max(1,g.products)}%;background:${familyColors[r.family_label]||'#9ba9bd'}"></span>`).join("")}</div></div>`;
    }).join("")}</div><div class="legend" style="margin-top:20px"><span class="legend-item"><span class="dot" style="background:#287f75"></span>Investimentos</span><span class="legend-item"><span class="dot" style="background:#6db2a6"></span>Cartões</span><span class="legend-item"><span class="dot" style="background:#9ba9bd"></span>Crédito e outros</span></div><div class="portfolio-card-footer"><div><strong>${fmt(sum(gs,'companies'))}</strong><span>empresas observadas</span></div><div><strong>${fmt(records)}</strong><span>registros de origem</span></div><div><strong>${fmt(gs.length)}</strong><span>conglomerados</span></div></div><div class="chart-foot"><span>Ofertas distintas por conteúdo, empresa e família.</span></div>`;
    const noMetrics = selected(D.coverage).filter(c=>c.family_label==='Métricas'&&!c.published).length;
    return `<div class="metrics-grid">${metric('Endpoints observados',fmt(endpoints),'',`<strong>${fmt(sum(gs,'http_ok'))} com HTTP 200</strong><span>no instantâneo</span>`,'endpoint',sum(gs,'http_ok')/endpoints*100)}${metric('Ofertas de produtos',fmt(products),'',`<strong>${fmt(sum(gs,'companies'))} empresas</strong><span>no perímetro observado</span>`,'portfolio',100)}${metric('Pontos de atendimento',fmt(physical),'',`<strong>${fmt(sum(gs,'branches'))} agências</strong><span>e rede complementar</span>`,'channels',100)}${metric('Coletas completas',fmt(success,1),'%',`<strong>${fmt(attention)} requerem atenção</strong><span>de ${fmt(endpoints)} endpoints</span>`,'quality',success,attention>0)}</div>
      <div class="overview-grid"><section class="executive-card"><div class="dark-eyebrow"><span class="live-dot"></span> LEITURA EXECUTIVA</div><h2>${attention?'Publicação ampla. <br>Confiabilidade desigual.':'Uma visão integrada<br>da publicação de mercado.'}</h2><p>${best?`<strong>${esc(best.label)}</strong> apresenta o maior índice técnico (${fmt(best.quality_score,1)}/100). ${gs.length>1?`A diferença para ${esc(worst.label)} é de <strong>${fmt(best.quality_score-worst.quality_score,1)} pontos</strong>.`:'O índice reflete os componentes disponíveis nesta coleta.'}`:''}</p><div class="hero-foot"><button class="hero-link" data-view="quality">Explorar evidências <span>→</span></button><span class="hero-tag">${date(D.meta.captured_to,{day:'2-digit',month:'short',timeZone:'America/Sao_Paulo'})} · BRASIL</span></div></section>${panel('Qualidade de publicação','Comparação entre conglomerados · escala de 0 a 100',rank,link('methodology','Critérios do índice'))}</div>
      <div class="two-columns">${panel('Cobertura por família','Presença de registros nos principais domínios',heatmap(),link('coverage','Ver 14 famílias'))}${panel('Dimensão do portfólio','Ofertas publicadas · comparação por volume',portfolio,link('portfolio','Explorar'))}</div>
      <div class="insight-strip"><span class="insight-icon">◈</span><div class="insight-content"><div class="insight-label">PONTO DE ATENÇÃO</div><p>${noMetrics?`${fmt(noMetrics)} conglomerado(s) sem registros de métricas operacionais.`:`${fmt(attention)} endpoints com coleta incompleta no perímetro selecionado.`} A resposta HTTP e a presença de dados são dimensões distintas de análise.</p></div>${link('quality','Analisar publicação')}</div>`;
  }

  function coverageView() {
    const cards=chosen().map(g=>`<article class="panel bank-card"><h3>${institution(g.group_id)}</h3><div class="bank-stat">${fmt(g.published_families)} <small>/ 14 famílias com dados</small></div><div class="metric-rule"><span style="width:${g.coverage_scope}%"></span></div><div class="bank-detail"><span>Sobre o escopo declarado</span><strong class="coverage-total">${pct(g.coverage_declared)}</strong></div></article>`).join("");
    return `<div class="detail-grid">${cards}</div>${panel('Mapa completo de publicação','Clique em uma célula para consultar os endpoints e as evidências da coleta.',heatmap(true),'','section-gap')}<div class="info-box">O denominador de 14 famílias é o escopo analítico deste estudo. A presença de dados não comprova conformidade regulatória. “Não declarado” significa ausência da família no catálogo observado.</div>`;
  }

  function catalogRows() {
    const q=state.search.toLocaleLowerCase('pt-BR');
    return selected(D.product_catalog).filter(r=>(state.family==='Todas'||r.family_label===state.family)&&(state.segment==='Todos'||r.segment===state.segment)&&(!q||[r.name,r.company,r.family_label,r.product_type].some(v=>String(v).toLocaleLowerCase('pt-BR').includes(q)))).sort((a,b)=>{
      const av=a[state.sort],bv=b[state.sort];
      return state.direction*(typeof av==='number'&&typeof bv==='number'?av-bv:String(av??'').localeCompare(String(bv??''),'pt-BR'));
    });
  }

  function portfolio() {
    const all=catalogRows(), pageSize=15;
    state.page=Math.min(state.page,Math.max(0,Math.ceil(all.length/pageSize)-1));
    const data=all.slice(state.page*pageSize,(state.page+1)*pageSize);
    return `<div class="view-toolbar"><input class="search" id="catalog-search" type="search" placeholder="Buscar produto, empresa ou modalidade…" aria-label="Buscar no portfólio" value="${esc(state.search)}"><label>Família<select class="select" id="catalog-family">${options(['Todas',...D.families.filter(f=>!['Canais','Métricas','Câmbio'].includes(f))],state.family)}</select></label><label>Segmento<select class="select" id="catalog-segment">${options(['Todos','PF','PJ','NA'],state.segment)}</select></label><span class="count-label">${fmt(all.length)} ofertas encontradas</span></div><section class="panel"><div class="header-note">Cada oferta preserva sua fonte. PF: pessoa física · PJ: pessoa jurídica · NA: segmento não definido pela rota.</div><div class="table-scroll"><table class="data-table"><thead><tr>${[['name','Produto / modalidade'],['group_id','Conglomerado'],['family_label','Família'],['segment','Segmento'],['rate_minimum','Taxa mínima']].map(([k,t])=>`<th aria-sort="${state.sort===k?(state.direction===1?'ascending':'descending'):'none'}"><button class="sort-button" data-sort="${k}">${t} ${state.sort===k?(state.direction===1?'↑':'↓'):'↕'}</button></th>`).join('')}<th></th></tr></thead><tbody>${data.map(r=>`<tr><td><button class="row-link" data-product="${r.entity_id}">${esc(r.name)}</button><div class="tiny">${esc(r.company)}</div></td><td>${institution(r.group_id)}</td><td>${esc(r.family_label)}</td><td>${badge(r.segment,'neutral')}</td><td class="numeric">${r.rate_minimum==null?'—':pct(r.rate_minimum,2)+' a.m.'}</td><td><button class="text-link" aria-label="Detalhar ${esc(r.name)}" data-product="${r.entity_id}">↗</button></td></tr>`).join('')}</tbody></table>${!all.length?empty('Nenhuma oferta corresponde aos filtros.'):''}</div><div class="table-pagination"><span>${all.length?fmt(state.page*pageSize+1):0}–${fmt(Math.min((state.page+1)*pageSize,all.length))} de ${fmt(all.length)} ofertas</span><div class="pagination-buttons"><button class="page-button" id="prev-page" ${state.page===0?'disabled':''}>← Anterior</button><button class="page-button" id="next-page" ${(state.page+1)*pageSize>=all.length?'disabled':''}>Próxima →</button></div></div></section><div class="info-box" style="margin-top:20px">Taxas exibidas somente quando pré-fixadas, em % ao mês e dentro dos critérios analíticos. Uma célula vazia significa ausência de taxa comparável. Ofertas com conteúdo idêntico na mesma empresa e família são deduplicadas.</div>`;
  }

  function rateRows() {
    return selected(D.rates_family).filter(r=>r.family_label===state.rateFamily&&r.segment===state.rateSegment&&r.unit===state.rateUnit&&r.indexer===state.rateIndexer&&r.product_type===state.rateType);
  }

  function rates() {
    const isMonthly=state.rateUnit==='pct_month';
    const indexers=[...new Set(selected(D.rates_family).filter(r=>r.unit===state.rateUnit).map(r=>r.indexer))].sort();
    if(!isMonthly&&indexers.length&&!indexers.includes(state.rateIndexer))state.rateIndexer=indexers[0];
    const types=[...new Set(selected(D.rates_family).filter(r=>r.family_label===state.rateFamily&&r.segment===state.rateSegment&&r.unit===state.rateUnit&&r.indexer===state.rateIndexer).map(r=>r.product_type))].sort();
    if(!types.includes(state.rateType))state.rateType=types[0]||'';
    const rs=rateRows(), max=Math.max(...rs.map(r=>r.p75||r.median||0),1)*1.2;
    const indexerName = indexerLabel(state.rateIndexer);
    const chart=rs.length?`<div class="rate-scale"><span>0</span><span>${fmt(max/2,1)}%</span><span>${fmt(max,1)}%</span></div>${rs.map(r=>`<div class="rate-row"><span>${institution(r.group_id)}</span><div class="range-track" aria-label="${esc(short[r.group_id])}: mediana ${pct(r.median,2)}, intervalo interquartil ${pct(r.p25,2)} a ${pct(r.p75,2)}"><div class="range-iqr" style="left:${100*r.p25/max}%;width:${100*(r.p75-r.p25)/max}%;background:${colors[r.group_id]}"></div><div class="range-dot" style="left:${100*r.median/max}%;background:${colors[r.group_id]}"></div></div><div class="rate-label">${pct(r.median,2)}<small>${fmt(r.offers)} ofertas</small></div></div>`).join('')}<div class="chart-foot"><span>● ${isMonthly?'Mediana das mínimas':'Mediana do fator do indexador'} · faixa: P25–P75</span><span>${isMonthly?'% ao mês':`% do indexador ${esc(indexerName)}`}</span></div>`:empty('Não há taxas comparáveis para esta combinação. Selecione outra família, segmento ou indexador.');
    const feeAll=selected(D.fees_family).filter(r=>r.family_label===state.rateFamily&&r.segment===state.rateSegment);
    const services=['Todos',...new Set(feeAll.map(r=>r.service))].sort();
    if(!services.includes(state.feeService))state.feeService='Todos';
    const feeRows=feeAll.filter(r=>state.feeService==='Todos'||r.service===state.feeService);
    return `<div class="view-toolbar"><label>Família<select class="select" id="rate-family">${options(D.families.filter(f=>!['Métricas','Canais','Câmbio'].includes(f)),state.rateFamily)}</select></label><label>Segmento<select class="select" id="rate-segment">${options(['PF','PJ','NA'],state.rateSegment)}</select></label><label>Modalidade<select class="select" id="rate-type">${options(types,state.rateType)}</select></label><label>Serviço de tarifa<select class="select" id="fee-service">${options(services,state.feeService)}</select></label><label>Unidade<select class="select" id="rate-unit"><option value="pct_month" ${isMonthly?'selected':''}>Pré-fixada · % a.m.</option><option value="pct_indexer" ${!isMonthly?'selected':''}>Pós-fixada · % do indexador</option></select></label>${!isMonthly?`<label>Indexador<select class="select" id="rate-indexer" ${!indexers.length?'disabled':''}>${indexers.length?indexers.map(v=>`<option value="${esc(v)}" ${v===state.rateIndexer?'selected':''}>${esc(indexerLabel(v))}</option>`).join(''):'<option>Sem dados</option>'}</select></label>`:''}</div><div class="info-box">A mediana compara <strong>${isMonthly?'taxas mínimas publicadas por oferta':'fatores publicados do indexador por oferta'}</strong>, sem ponderação por saldo, volume ou perfil de cliente. A modalidade selecionada delimita a comparação de taxas; tarifas são separadas por código e serviço. Esta leitura não representa o custo efetivo do crédito nem um ranking de preços praticados.</div>${panel(isMonthly?'Distribuição das taxas mínimas':'Percentuais do indexador publicados',`${esc(state.rateFamily)} · ${esc(state.rateSegment)} · ${isMonthly?'pré-fixada, % ao mês':`% do indexador ${esc(indexerName)}`}`,chart,'','section-gap')}
      <section class="panel section-gap"><div class="panel-header"><div><h2>Amostra e dispersão</h2><p class="panel-subtitle">Uma observação por oferta e indexador · zeros e faixas inválidas excluídos</p></div></div><div class="table-scroll" style="margin-top:18px"><table class="data-table"><thead><tr><th>Conglomerado</th><th>Ofertas</th><th>Mínima</th><th>P25</th><th>Mediana</th><th>P75</th><th>Máxima publicada</th></tr></thead><tbody>${rs.map(r=>`<tr><td>${institution(r.group_id)}</td><td>${fmt(r.offers)}</td><td>${pct(r.minimum,2)}</td><td>${pct(r.p25,2)}</td><td><strong>${pct(r.median,2)}</strong></td><td>${pct(r.p75,2)}</td><td>${pct(r.maximum,2)}</td></tr>`).join('')}</tbody></table></div></section>
      ${panel('Tarifas por família e segmento','Mínimos por código de serviço e moeda; faixas inválidas excluídas. Zero não significa gratuidade irrestrita.',feeRows.length?`<div class="table-scroll"><table class="data-table"><thead><tr><th>Conglomerado</th><th>Serviço / código</th><th>Itens</th><th>Mínimo zero</th><th>Mediana mínima</th><th>Máximo</th></tr></thead><tbody>${feeRows.map(r=>`<tr><td>${institution(r.group_id)}</td><td>${esc(r.service)}<small> · ${esc(r.code)}</small></td><td>${fmt(r.count)}</td><td>${fmt(r.zero_minimum)}</td><td>${esc(r.currency)} ${fmt(r.median,2)}</td><td>${esc(r.currency)} ${fmt(r.maximum,2)}</td></tr>`).join('')}</tbody></table></div>`:empty('Nenhuma tarifa publicada neste recorte.'))}`;
  }

  function channels() {
    const channelColors={"Agências":"#287f75","Correspondentes":"#89baad","ATMs":"#d4b87d","Digitais":"#8e9fb9","Telefônicos":"#c5cdd6"};
    const cs=selected(D.channels_type), max=Math.max(...chosen().map(g=>g.channels),1);
    const chart=chosen().map(g=>`<div class="channel-row">${institution(g.group_id)}<div class="stacked-track" style="width:${100*g.channels/max}%">${cs.filter(r=>r.group_id===g.group_id).map(r=>`<span title="${esc(r.channel_type)}: ${fmt(r.count)}" style="width:${100*r.count/g.channels}%;background:${channelColors[r.channel_type]||'#ccc'}"></span>`).join('')}</div><strong>${fmt(g.channels)}</strong></div>`).join('');
    const ufs=[...new Set(D.channels_uf.map(r=>r.uf))].sort();
    const regional=ufs.filter(uf=>state.uf==='Todas'||uf===state.uf).map(uf=>({uf,values:chosen().map(g=>({group_id:g.group_id,count:sum(D.channels_uf.filter(r=>r.uf===uf&&r.group_id===g.group_id),'count')}))})).sort((a,b)=>sum(b.values,'count')-sum(a.values,'count'));
    return `<div class="metrics-grid">${metric('Rede física',fmt(sum(chosen(),'physical_channels')),'','Agências, ATMs e correspondentes','channels')}${metric('Agências',fmt(sum(chosen(),'branches')),'','Pontos deduplicados por empresa','channels')}${metric('Correspondentes',fmt(sum(chosen(),'agents')),'','Locais declarados pelas instituições','channels')}${metric('ATMs compartilhados',fmt(sum(chosen(),'atms')),'','Ausência de dados não significa ausência de rede','channels')}</div>${panel('Composição da rede','Todos os canais normalizados · incluindo digitais e telefônicos',chart+`<div class="legend">${Object.entries(channelColors).map(([name,color])=>`<span class="legend-item"><span class="dot" style="background:${color}"></span>${name}</span>`).join('')}</div>`,'','section-gap')}<div class="view-toolbar"><label>Unidade federativa<select class="select" id="uf-filter">${options(['Todas',...ufs],state.uf)}</select></label><span class="count-label">Rede física com UF válida · ordenada pelo volume total</span></div><section class="panel"><div class="table-scroll"><table class="data-table"><thead><tr><th>UF</th>${chosen().map(g=>`<th>${institution(g.group_id)}</th>`).join('')}<th>Total de vínculos</th></tr></thead><tbody>${regional.map(r=>`<tr><td><strong>${r.uf}</strong></td>${r.values.map(v=>`<td>${fmt(v.count)}</td>`).join('')}<td><strong>${fmt(sum(r.values,'count'))}</strong></td></tr>`).join('')}</tbody></table></div></section><div class="info-box" style="margin-top:20px">Contagem de vínculos de atendimento por empresa. Um mesmo local pode atender mais de uma empresa ou conglomerado. O total não representa locais físicos exclusivos no Brasil.</div>`;
  }

  function exchange() {
    const rs=selected(D.exchange);
    return panel('Cotações online e VET','Linhas separadas por moeda, operação e forma de entrega. VET é uma distribuição, sem imputar cotação única.',`<div class="table-scroll"><table class="data-table"><thead><tr><th>Instituição</th><th>Moeda / operação</th><th>Entrega / público</th><th>Cotação online</th><th>VET mínimo–máximo</th><th>Faixa / atualização</th></tr></thead><tbody>${rs.map(r=>`<tr><td>${institution(r.group_id)}</td><td>${esc(r.currency)} · ${esc(r.transaction_type)}</td><td>${esc(r.delivery)}<div class="tiny">${esc(r.audience)}</div></td><td>${fmt(r.value,6)}</td><td>${r.vet_minimum==null?'—':fmt(r.vet_minimum,6)+' – '+fmt(r.vet_maximum,6)}</td><td>${esc(r.range_category||r.updated_at)}<details><summary>Evidência / distribuição</summary><p class="break-code">${esc(r.source_sha)}</p><pre>${esc(r.vet_prices)}</pre></details></td></tr>`).join('')}</tbody></table></div>`);
  }

  function incidentRows() {
    return selected(D.endpoints).filter(e=>state.incident==='Todos'?(!e.complete||e.records===0||!e.tls_verified):state.incident==='Incompletos'?!e.complete:state.incident==='Sem dados'?e.records===0:!e.tls_verified).sort((a,b)=>a.status-b.status||a.group_id.localeCompare(b.group_id));
  }

  function quality() {
    const components=[['collection_score','Coleta completa'],['data_score','Presença de dados'],['geography_score','UF da rede física'],['rate_score','Ofertas de crédito com taxa']];
    const cards=chosen().map(g=>`<article class="panel bank-card"><h3>${institution(g.group_id)}</h3><div class="bank-stat">${fmt(g.quality_score,1)} <small>/ 100 · índice técnico</small></div><div class="quality-components">${components.map(([k,label])=>`<div><div class="component-label"><span>${label}</span><strong>${pct(g[k])}</strong></div><div class="component-track"><span style="width:${g[k]||0}%"></span></div></div>`).join('')}</div></article>`).join('');
    const incidents=incidentRows();
    return `<div class="detail-grid">${cards}</div><div class="info-box">Índice versão ${esc(D.meta.transform_version)}: média simples de quatro componentes disponíveis. Denominadores ausentes são ignorados. “Coleta completa” exige HTTP 200 e ausência de erro ou truncamento. O índice mede a publicação técnica observada.</div>${panel('Contratos e controles','Verificações do snapshot completo · não variam com o filtro de conglomerados',`<div class="check-list">${D.quality.map(c=>`<div class="check-row"><span class="check-icon ${c.passed?'':'warn'}">${c.passed?'✓':'◈'}</span><span>${esc(c.label)}</span>${badge(c.passed?'Aprovado':`${fmt(c.failures)} ocorrências`,c.passed?'':c.severity==='error'?'danger':'warn')}</div>`).join('')}</div>`,'','section-gap')}
      <div class="view-toolbar"><label>Ocorrências<select class="select" id="incident-filter">${options(['Todos','Incompletos','Sem dados','TLS não verificado'],state.incident)}</select></label><span class="count-label">${fmt(incidents.length)} endpoints no recorte</span></div><section class="panel"><div class="table-scroll"><table class="data-table"><thead><tr><th>Instituição / família</th><th>Conglomerado</th><th>HTTP</th><th>Registros</th><th>Condição</th><th></th></tr></thead><tbody>${incidents.map(e=>`<tr><td><button class="row-link" data-endpoint="${e.endpoint_id}">${esc(e.company)}</button><div class="tiny">${esc(e.family_label)}</div></td><td>${institution(e.group_id)}</td><td>${badge(e.status||'Rede',e.status===200?'':'danger')}</td><td>${fmt(e.records)}</td><td>${badge(!e.complete?'Incompleto':e.records===0?'Sem dados':'TLS não verificado','warn')}</td><td><button class="text-link" data-endpoint="${e.endpoint_id}" aria-label="Detalhar endpoint de ${esc(e.company)}">↗</button></td></tr>`).join('')}</tbody></table>${!incidents.length?empty('Nenhuma ocorrência neste recorte.'):''}</div></section>`;
  }

  function methodology() {
    return `<div class="methodology-grid"><section class="panel prose"><h2>Da publicação à decisão</h2><p>Este observatório compara os dados públicos de Santander, Itaú Unibanco e Bradesco e das empresas incluídas no perímetro observado. A fonte é a publicação das instituições nas APIs de Dados Abertos do Open Finance Brasil.</p><h3>Definições das métricas</h3>
      <div class="definition"><strong>Ofertas de produtos</strong><p>Conteúdos distintos de produto por empresa e família. Seguros, previdência e capitalização são expandidos por produto. O mesmo nome pode identificar ofertas diferentes. A identidade é técnica, não um código comercial universal.</p></div>
      <div class="definition"><strong>Cobertura do escopo e declarada</strong><p>Famílias com pelo menos um registro e HTTP 200 ÷ 14 famílias do estudo. Cobertura declarada usa como denominador as famílias presentes no catálogo observado. Não é uma avaliação de conformidade regulatória.</p></div>
      <div class="definition"><strong>Coletas completas</strong><p>Endpoints com HTTP 200, sem erro nem truncamento ÷ endpoints tentados. HTTP 200 com zero registros pode ser completo, mas não conta como presença de dados.</p></div>
      <div class="definition"><strong>Índice técnico de qualidade</strong><p>Média de: coleta completa / total; endpoints HTTP 200 com dados / endpoints HTTP 200; locais físicos com UF válida / locais físicos; ofertas de crédito com taxa válida / ofertas de crédito. Componentes sem denominador são nulos e não entram na média. Escala 0–100. Versão ${esc(D.meta.transform_version)}.</p></div>
      <div class="definition"><strong>Taxas comparáveis</strong><p>O valor decimal da API é multiplicado por 100, sem inferir a unidade pela magnitude. Pré-fixadas de crédito: minimumRate em % a.m., mínimo &gt; 0 e ≤ 50. Pós-fixadas: campo rate como percentual do indexador, &gt; 0 e ≤ 300. MinimumRate de uma taxa pós-fixada não é tratado como percentual do indexador. Indexadores diferentes são separados. Faixas invertidas e unidades desconhecidas são excluídas. Medianas de applications não substituem mínimos ausentes ou zerados.</p><p>A distribuição usa uma observação por oferta e indexador. As famílias podem reunir modalidades diferentes. Não há ponderação por carteira, perfil de risco ou volume.</p></div>
      <div class="definition"><strong>Rede de atendimento</strong><p>Correspondentes são expandidos por local. Deduplicação por empresa, família, identificação e endereço. Uma mesma localização pode permanecer em empresas diferentes. Canais digitais e telefônicos ficam fora do indicador de rede física.</p></div>
      <h3>Limites de interpretação</h3><ul><li>Dados de clientes, consentimentos e pagamentos não integram este estudo.</li><li>Tarifas e taxas publicadas não equivalem à negociação ou precificação efetiva.</li><li>O Diretório não comprova vínculo societário. Domínio e CNPJ curado são evidências operacionais.</li><li>O instantâneo importado preserva a resolução de conglomerados da origem. Uma nova descoberta registra sua própria evidência.</li><li>Não há série histórica nesta publicação; diferenças no tempo não são estimadas.</li><li>Uma coleta sem dados pode refletir ausência legítima de oferta ou falha de publicação.</li></ul>
      <h3>Referências oficiais</h3><p><a href="https://openfinancebrasil.atlassian.net/wiki/pages/viewpage.action?pageId=182845448" target="_blank" rel="noopener">Open Finance Brasil · Dados Abertos ↗</a><br><a href="https://data.directory.openbankingbrasil.org.br/participants" target="_blank" rel="noopener">Diretório de participantes ↗</a><br><a href="https://github.com/OpenBanking-Brasil/openapi" target="_blank" rel="noopener">Especificações OpenAPI oficiais ↗</a></p></section>
      <div><section class="panel prose section-gap"><div class="eyebrow">EVIDÊNCIA DE ORIGEM</div><h2>Ficha do instantâneo</h2><div class="definition"><strong>Janela da coleta</strong><p>${dateTime(D.meta.captured_from)}<br>a ${dateTime(D.meta.captured_to)}<br>Horário de Brasília</p></div><div class="definition"><strong>Origem</strong><p>${D.meta.origin==='imported_snapshot'?'Reprocessamento de bronze existente. Esta entrega não executou uma nova coleta remota.':'Coleta direta das APIs públicas.'}</p></div><div class="definition"><strong>Snapshot</strong><p class="break-code">${esc(D.meta.snapshot_id)}</p></div><div class="definition"><strong>Build</strong><p class="break-code">${esc(D.meta.build_id)}</p></div><div class="definition"><strong>Fingerprint SHA-256</strong><p class="break-code">${esc(D.meta.source_fingerprint)}</p></div><div class="definition"><strong>Processado em</strong><p>${dateTime(D.meta.generated_at)}</p></div><div class="definition"><strong>Volume de origem</strong><p>${fmt(D.meta.bronze_bytes/1e6,1)} MB · ${fmt(D.endpoints.length)} endpoints</p></div></section><section class="panel prose"><h2>Rastreabilidade</h2><p>Cada oferta e endpoint expõe sua URL de origem e hash do objeto bronze no painel de detalhes. O artefato funciona offline e não consulta serviços externos ao abrir.</p><p>Os dados completos deste painel estão em <a href="dashboard.json" download="observatory-snapshot.json">dashboard.json ↓</a>. A exportação CSV respeita a visão e os filtros atuais.</p></section></div></div>`;
  }

  function render(preserveFocus=false) {
    const focus=document.activeElement?.id, sortFocus=document.activeElement?.dataset?.sort, start=document.activeElement?.selectionStart;
    const [label,title,sub]=views[state.view];
    $("#breadcrumb-view").textContent=label; $("#page-title").textContent=title; $("#page-subtitle").textContent=sub;
    document.title=`${label} — Observatory`;
    $("#navigation").innerHTML=Object.entries(views).map(([key,[name]])=>`<a class="nav-item ${key===state.view?'active':''}" href="#${key}" ${key===state.view?'aria-current="page"':''}>${icon(key)}<span>${name}</span>${key==='quality'?`<span class="nav-count">${sum(chosen(),'attention')}</span>`:''}</a>`).join('');
    $("#selected-count").textContent=`${state.groups.size} selecionado${state.groups.size===1?'':'s'}`;
    $("#group-popover").innerHTML=D.group_metrics.map(g=>`<label><input type="checkbox" data-group-toggle="${g.group_id}" ${state.groups.has(g.group_id)?'checked':''}>${institution(g.group_id)}</label>`).join('')+'<p>Selecione ao menos um conglomerado.</p>';
    const functions={overview,coverage:coverageView,portfolio,rates,channels,exchange,quality,methodology};
    $("#view").innerHTML=functions[state.view]();
    if(!preserveFocus){$("#view").classList.remove('view-enter');void $("#view").offsetWidth;$("#view").classList.add('view-enter');}
    if(preserveFocus&&sortFocus)document.querySelector(`[data-sort="${sortFocus}"]`)?.focus();
    if(preserveFocus&&focus){const target=document.getElementById(focus);if(target){target.focus();if(start!=null&&target.type==='search')target.setSelectionRange(start,start);}}
  }

  let returnFocus;
  function openDrawer(html) {
    returnFocus=document.activeElement;
    $("#drawer").innerHTML=`<button class="drawer-close" id="close-drawer" aria-label="Fechar detalhamento">×</button>${html}`;
    $("#drawer").hidden=false;$("#drawer-backdrop").hidden=false;document.body.style.overflow='hidden';
    $(".shell").inert=true;$("#sidebar").inert=true;$("#close-drawer").focus();
  }
  function closeDrawer(){ $("#drawer").hidden=true;$("#drawer-backdrop").hidden=true;document.body.style.overflow='';$(".shell").inert=false;$("#sidebar").inert=false;returnFocus?.focus(); }
  function safeUrl(url) { try {return new URL(url).protocol==='https:'?esc(url):'#';} catch{return '#';} }
  function endpointDetails(e) {
    return `<div class="drawer-item"><h3>${esc(e.company)}</h3><p>${esc(e.family)} · ${badge(e.status?`HTTP ${e.status}`:'Falha de rede',e.status===200?'':'danger')} ${badge(e.complete?'Completo':'Incompleto',e.complete?'':'warn')}</p><dl><dt>Registros de origem</dt><dd>${fmt(e.records)}</dd><dt>Páginas de dados</dt><dd>${fmt(e.pages)}</dd><dt>TLS na origem</dt><dd>${e.tls_verified?'Verificado':'Sem verificação — evidência legada'}</dd><dt>Condição da coleta</dt><dd>${esc(e.error||'Sem erro registrado')}</dd><dt>Coletado em</dt><dd>${dateTime(e.captured_at)}</dd><dt>SHA-256 do objeto</dt><dd class="break-code">${esc(e.source_sha||'Consulte o log de páginas bronze')}</dd></dl><a class="url" href="${safeUrl(e.url)}" target="_blank" rel="noopener">${esc(e.url)} ↗</a></div>`;
  }
  function coverageDrawer(group,family){
    const endpoints=D.endpoints.filter(e=>e.group_id===group&&e.family_label===family);
    openDrawer(`<div class="eyebrow">EVIDÊNCIA DE PUBLICAÇÃO</div><h2>${esc(family)}</h2><p>${institution(group)} · ${fmt(endpoints.length)} endpoints no catálogo observado.</p>${endpoints.map(endpointDetails).join('')||empty('Família não declarada no catálogo observado. Ausência no catálogo não comprova ausência de oferta.')}`);
  }
  function productDrawer(id){
    const p=D.product_catalog.find(r=>r.entity_id===id); if(!p)return;
    openDrawer(`<div class="eyebrow">OFERTA PUBLICADA</div><h2>${esc(p.name)}</h2><p>${institution(p.group_id)} · ${esc(p.family_label)}</p><dl><dt>Empresa</dt><dd>${esc(p.company)}</dd><dt>CNPJ</dt><dd>${esc(p.cnpj)}</dd><dt>Marca</dt><dd>${esc(p.brand||'Não informada')}</dd><dt>Tipo</dt><dd>${esc(p.product_type||'Não informado')}</dd><dt>Segmento da rota</dt><dd>${esc(p.segment)}</dd><dt>Taxa mínima pré</dt><dd>${p.rate_minimum==null?'Sem taxa comparável':pct(p.rate_minimum,2)+' a.m.'}</dd><dt>Taxa máxima pré</dt><dd>${p.rate_maximum==null?'Sem taxa comparável':pct(p.rate_maximum,2)+' a.m.'}</dd><dt>Identidade da oferta</dt><dd class="break-code">${esc(p.entity_id)}</dd><dt>SHA-256 bronze</dt><dd class="break-code">${esc(p.source_sha)}</dd></dl><div class="info-box">Faixas publicadas não representam a taxa efetivamente contratada. Consulte o contexto e as condições da oferta na instituição.</div><h3>Fonte primária</h3><a class="url" href="${safeUrl(p.source_url)}" target="_blank" rel="noopener">${esc(p.source_url)} ↗</a>`);
  }
  function toast(message){$("#toast").textContent=message;$("#toast").hidden=false;setTimeout(()=>$("#toast").hidden=true,3500);}
  function csvCell(value){let v=String(value??'');if(/^[=+@\-\t\r]/.test(v))v="'"+v;return '"'+v.replace(/"/g,'""')+'"';}
  function exportData(){
    const data=state.view==='portfolio'?catalogRows():state.view==='coverage'?selected(D.coverage):state.view==='rates'?[...rateRows().map(r=>({kind:'taxa',...r})),...selected(D.fees_family).filter(r=>r.family_label===state.rateFamily&&r.segment===state.rateSegment&&(state.feeService==='Todos'||r.service===state.feeService)).map(r=>({kind:'tarifa',...r}))]:state.view==='channels'?selected(D.channels_uf).filter(r=>state.uf==='Todas'||r.uf===state.uf):state.view==='quality'?incidentRows():state.view==='exchange'?selected(D.exchange):state.view==='methodology'?[D.meta]:chosen();
    if(!data.length){toast('Não há registros para exportar neste recorte.');return;}
    const keys=[...new Set(data.flatMap(r=>Object.keys(r)))];
    const csv='\ufeff'+[keys.map(csvCell).join(';'),...data.map(r=>keys.map(k=>csvCell(typeof r[k]==='object'?JSON.stringify(r[k]):r[k])).join(';'))].join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));
    const a=document.createElement('a');a.href=url;a.download=`observatory-${state.view}-${D.meta.build_id.slice(0,8)}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast(`${fmt(data.length)} registros exportados com os filtros atuais.`);
  }
  function navigate(view){if(!views[view])return;if(location.hash.slice(1)!==view)location.hash=view;else{state.view=view;state.page=0;render();}$("#sidebar").classList.remove('mobile-open');$("#mobile-menu").setAttribute('aria-expanded','false');}
  document.addEventListener('click',e=>{
    if(e.target.closest('.skip')){e.preventDefault();$('#content').focus();return;}
    const view=e.target.closest('[data-view]');if(view){navigate(view.dataset.view);return;}
    const coverage=e.target.closest('[data-coverage]');if(coverage){coverageDrawer(coverage.dataset.group,coverage.dataset.coverage);return;}
    const product=e.target.closest('[data-product]');if(product){productDrawer(product.dataset.product);return;}
    const endpoint=e.target.closest('[data-endpoint]');if(endpoint){const row=D.endpoints.find(r=>r.endpoint_id===endpoint.dataset.endpoint);if(row)openDrawer(`<div class="eyebrow">EVIDÊNCIA DA COLETA</div><h2>${esc(row.family_label)}</h2>${endpointDetails(row)}`);return;}
    const sort=e.target.closest('[data-sort]');if(sort){state.direction=state.sort===sort.dataset.sort?-state.direction:1;state.sort=sort.dataset.sort;state.page=0;render(true);return;}
    if(e.target.closest('#close-drawer')||e.target.id==='drawer-backdrop')closeDrawer();
    if(e.target.id==='prev-page'){state.page--;render();}
    if(e.target.id==='next-page'){state.page++;render();}
    for(const [button,popover] of [['#group-filter','#group-popover'],['#snapshot-button','#snapshot-popover']]){
      if(e.target.closest(button)){const hidden=$(popover).hidden;$(popover).hidden=!hidden;$(button).setAttribute('aria-expanded',String(hidden));}
      else if(!e.target.closest(popover)){$(popover).hidden=true;$(button).setAttribute('aria-expanded','false');}
    }
  });
  document.addEventListener('change',e=>{
    const t=e.target;
    if(t.dataset.groupToggle){if(!t.checked&&state.groups.size===1){t.checked=true;toast('Mantenha ao menos um conglomerado selecionado.');return;}const id=t.dataset.groupToggle;t.checked?state.groups.add(id):state.groups.delete(id);render();document.querySelector(`[data-group-toggle="${id}"]`)?.focus();return;}
    const mapping={'catalog-family':'family','catalog-segment':'segment','rate-type':'rateType','fee-service':'feeService','rate-family':'rateFamily','rate-segment':'rateSegment','rate-unit':'rateUnit','rate-indexer':'rateIndexer','uf-filter':'uf','incident-filter':'incident'};
    if(mapping[t.id]){state[mapping[t.id]]=t.value;state.page=0;
      if(t.id==='rate-unit')state.rateIndexer=t.value==='pct_month'?'PRE_FIXADO':([...new Set(selected(D.rates_family).filter(r=>r.unit===t.value).map(r=>r.indexer))].sort()[0]||'CDI');
      render(true);document.getElementById(t.id)?.focus();}
  });
  document.addEventListener('input',e=>{if(e.target.id==='catalog-search'){state.search=e.target.value;state.page=0;render(true);}});
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape'){if(!$("#drawer").hidden)closeDrawer();for(const p of ['#group-popover','#snapshot-popover'])$(p).hidden=true;$("#group-filter").setAttribute('aria-expanded','false');$("#snapshot-button").setAttribute('aria-expanded','false');$("#sidebar").classList.remove('mobile-open');$("#mobile-menu").setAttribute('aria-expanded','false');}
    if(e.key==='Tab'&&!$("#drawer").hidden){const targets=[...$("#drawer").querySelectorAll('button,a[href],input,select,[tabindex="0"]')];const first=targets[0],last=targets.at(-1);if(e.shiftKey&&document.activeElement===first){last?.focus();e.preventDefault();}else if(!e.shiftKey&&document.activeElement===last){first?.focus();e.preventDefault();}}
  });
  $("#export-button").addEventListener('click',exportData);
  $("#print-button").addEventListener('click',()=>{if(state.view!=='overview'){state.view='overview';location.hash='overview';render();}window.print();});
  $("#mobile-menu").addEventListener('click',()=>{const open=$("#sidebar").classList.toggle('mobile-open');$("#mobile-menu").setAttribute('aria-expanded',String(open));});
  $("#snapshot-date").textContent=date(D.meta.captured_to);
  $("#snapshot-popover").innerHTML=`<h3>Instantâneo observado</h3><p>${dateTime(D.meta.captured_from)} a ${dateTime(D.meta.captured_to)} · Brasília</p><p style="margin-top:8px">${D.meta.origin==='imported_snapshot'?'Bronze existente, reprocessado nesta versão.':'Coleta direta das APIs.'} Uma única janela disponível; sem série histórica.</p><p class="break-code" style="margin-top:8px">Build ${esc(D.meta.build_id)}</p>`;
  $("#footer-snapshot").textContent=`Coleta: ${date(D.meta.captured_to)} · Critérios v${D.meta.transform_version}`;
  window.addEventListener('hashchange',()=>{state.view=views[location.hash.slice(1)]?location.hash.slice(1):'overview';state.page=0;render();window.scrollTo({top:0,behavior:'instant'});});
  state.view=views[location.hash.slice(1)]?location.hash.slice(1):'overview';render();
})();
