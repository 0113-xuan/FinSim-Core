(function(root) {
  'use strict';
  function mount({after,ctx,getRequest}) {
    const Q=root.QAModel,S=root.FutureWalletShell,document=root.document;
    const element=(tag,text)=>{const node=document.createElement(tag);if(text!=null)node.textContent=text;return node;};
    const section=element('section'),heading=element('h3','問問題'),mode=element('small');
    section.id='qaSection';section.setAttribute('aria-labelledby','qaHeading');heading.id='qaHeading';mode.hidden=true;heading.append(mode);
    const hint=element('p','可以先問名詞與資料來源；執行模擬後，也能問這次計畫的結果。點範例問題只會填入文字，按「送出」才會送出。');
    const examples=element('div');examples.className='qa-questions';examples.setAttribute('aria-label','範例問題');
    const form=element('form'),fieldset=element('fieldset'),label=element('label','你的問題'),input=element('textarea');
    input.id='qaQuestion';input.maxLength=Q.MAX_QUESTION_LENGTH;input.rows=2;input.required=true;
    input.placeholder='例如：為什麼我的最低現金會出現在這個月？';input.setAttribute('aria-describedby','qaCount qaPrivacy');label.htmlFor=input.id;
    const controls=element('div'),count=element('small'),submit=element('button','送出');
    controls.className='qa-controls';count.id='qaCount';count.setAttribute('aria-live','polite');submit.type='submit';submit.className='primary';
    controls.append(count,submit);fieldset.append(label,input,controls);form.append(fieldset);
    const privacy=element('p'),privacyText=element('small','按下後，會把你的問題和相關的說明資料傳給 Google Gemini 產生回答；沒有啟用 AI 時不會傳出任何資料。');
    privacy.id='qaPrivacy';privacy.append(privacyText,element('small','模擬完成後也會附上這次計畫的事實表，不含帳號資料。'));
    const result=element('div');result.id='qaResult';result.setAttribute('aria-live','polite');result.setAttribute('aria-atomic','true');
    // The disclosure comes before anything that can send, so it is read first.
    section.append(heading,hint,privacy,examples,form,result);after.after(section);
    let sending=false,version=0,active=null;
    function sync(){const state=Q.questionState(input.value);count.textContent=`還可輸入 ${Math.max(0,state.remaining)} 字`;submit.disabled=sending||!state.valid;}
    function buttons(parent,items){
      for(const question of Q.questions(items)){
        const button=element('button',question);button.type='button';button.disabled=sending;
        button.addEventListener('click',()=>{if(sending||ctx.busy)return;input.value=question;sync();input.focus();});parent.append(button);
      }
    }
    function clear(){version++;active?.abort();result.replaceChildren();mode.hidden=true;}
    function render(data){
      result.replaceChildren();mode.hidden=data.source!=='extractive';mode.textContent='（直接引用資料）';
      if(data.source==='extractive')result.append(element('p',Q.fallbackNotice(data.fallback_reason)));
      result.append(...Q.answerNodes(document,data));
      const citations=Q.citationRows(data.citations);
      if(citations.length){
        const list=element('ul');list.className='qa-citations';
        for(const citation of citations)list.append(element('li',citation.text));
        result.append(element('h4','資料來源'),list);
      }
      if(data.source==='no_basis'){
        const suggestions=element('div');suggestions.className='qa-questions';buttons(suggestions,data.suggested_questions);result.append(suggestions);
      }else if(data.follow_ups?.length){
        const followUps=element('div');followUps.className='qa-questions';buttons(followUps,data.follow_ups);result.append(element('h4','可以接著問'),followUps);
      }
      const disclaimer=element('p');disclaimer.append(element('small',data.disclaimer));result.append(disclaimer);
    }
    function send(){
      if(sending||ctx.busy||!Q.questionState(input.value).valid)return;
      const question=Q.questionState(input.value).question;
      const work=ctx.perform(async()=>{
        clear();const requestVersion=version;const payload={...getRequest(),question};
        sending=true;sync();result.textContent='正在查找依據…';result.setAttribute('aria-busy','true');
        const controller=new AbortController();active=controller;ctx.controllers.add(controller);
        const timeout=root.setTimeout(()=>controller.abort(),20000);
        try{
          const response=await root.fetch('/ai/plan-qa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
          let data;try{data=await response.json();}catch(_){throw new Error('問答回應無法讀取，請重新送出');}
          if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:`問答未完成（HTTP ${response.status}），請稍後重試`);
          if(ctx.alive&&version===requestVersion){render(data);S.status('回答已顯示。');}
        }catch(error){
          if(ctx.alive&&version===requestVersion){result.replaceChildren();if(error.name==='AbortError')throw new Error('問答逾時或已取消，請重新送出');throw error;}
        }finally{
          root.clearTimeout(timeout);ctx.controllers.delete(controller);active=null;sending=false;result.removeAttribute('aria-busy');
        }
      });
      Promise.resolve(work).finally(()=>{if(ctx.alive){sync();for(const button of section.querySelectorAll('.qa-questions button'))button.disabled=false;}});
    }
    input.addEventListener('input',sync);form.addEventListener('submit',event=>{event.preventDefault();send();});
    buttons(examples,Q.EXAMPLES);sync();return {clear};
  }
  root.PlanQAForm={mount};
})(globalThis);
