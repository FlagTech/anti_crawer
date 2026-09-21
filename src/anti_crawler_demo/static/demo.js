const demo=document.body.dataset.demo,table=document.querySelector('#dataset-table'),datasetState=document.querySelector('#dataset-state'),origin=location.origin,url=`${origin}/${demo}`;
/* Server-rendered in demo.html; retained client-side data is intentionally disabled. */
/* const techniqueInfo={
 'rate-limit':{name:'滑動視窗限流',detail:'索引頁與所有報告詳情頁共用 10 秒最多 5 次的配額；超限時整個 HTML 回應為 429，並附 Retry-After。',pass:'使用同一個 cookie session 追蹤連結；收到 429 時讀取 Retry-After、等待指定秒數後再重試。'},
 'header-policy':{name:'導覽標頭檢查',detail:'整個 HTML 頁面要求 Accept: text/html 與瀏覽器樣式 User-Agent；缺少任一項即回傳 403。',pass:'在受控測試中，設定網站要求的 HTML Accept 與 User-Agent，再解析回傳的整頁表格。'},
 'session-gate':{name:'Session gate',detail:'資料表只會出現在已有本站示範 session cookie 的整頁 HTML；沒有 session 時回傳 401。',pass:'先造訪 /session-gate/start 建立 session，並在後續請求保存與帶回 cookie。'},
 'deferred-content':{name:'動態資料載入',detail:'初始 HTML 只有表格結構，資料列由頁面 JavaScript 自動非同步載入。',pass:'使用可執行 JavaScript 的瀏覽器自動化工具，例如 Playwright，等待 tbody 的資料列出現。'},
 'js-token':{name:'JavaScript 短效 token',detail:'初始 HTML 不含資料列；頁面 JavaScript 取得一次性短效 token 後才載入表格。',pass:'使用瀏覽器環境讓頁面正常執行 token 流程，並等待資料列渲染完成。'},
 'captcha-sim':{name:'互動 challenge 模擬',detail:'資料表需在頁面完成受控的一次性 challenge 流程後才出現。',pass:'使用瀏覽器自動化執行頁面流程並等待 challenge 後的資料表；此站僅為本機訓練模擬。'},
 'robots-honeypot':{name:'robots.txt 與 honeypot',detail:'一般資料頁可讀取，但 robots.txt 禁止的 /training-honeypot 會記錄並以 403 回應。',pass:'爬蟲先讀取 robots.txt、排除禁止路徑，只抓取一般資料頁與已發現的正常連結。'},
 'browser-integrity':{name:'瀏覽器完整性訊號',detail:'資料列需等待頁面送出 JavaScript、storage、viewport、語言與指標等一致性訊號後才載入。',pass:'使用實際瀏覽器引擎執行頁面；不要把單純 HTTP client 當成能提供完整瀏覽器能力的工具。'}
};
const techniqueNote=document.querySelector('#technique-note'),info=techniqueInfo[demo];
techniqueNote.replaceChildren(Object.assign(document.createElement('strong'),{textContent:`本例技術：${info.name}`}),document.createElement('br'),document.createTextNode(`檢查內容：${info.detail} 合規取得方式：${info.pass}`)); */
const staticParser=`import requests\nfrom bs4 import BeautifulSoup\nr = requests.get('${url}')\nsoup = BeautifulSoup(r.text, 'html.parser')\nprint(r.status_code, [row.get_text(' ', strip=True) for row in soup.select('#dataset-table tbody tr')])`;
const browserParser=`from playwright.sync_api import sync_playwright\nwith sync_playwright() as p:\n    browser = p.chromium.launch()\n    page = browser.new_page()\n    page.goto('${url}')\n    page.locator('#dataset-table:not([hidden]) tbody tr').first.wait_for()\n    print(page.locator('#dataset-table tbody tr').all_inner_texts())\n    browser.close()`;
const captchaParser=`import re\nfrom playwright.sync_api import sync_playwright\nwith sync_playwright() as p:\n    browser = p.chromium.launch()\n    page = browser.new_page()\n    page.goto('${url}')\n    prompt = page.locator('#captcha-prompt').inner_text()\n    answer = sum(map(int, re.findall(r'\\d+', prompt)))\n    page.locator('#captcha-answer').fill(str(answer))\n    page.locator('#captcha-submit').click()\n    page.locator('#dataset-table:not([hidden]) tbody tr').first.wait_for()\n    print(page.locator('#dataset-table tbody tr').all_inner_texts())\n    browser.close()`;
const curlCffiParser=`from pathlib import Path\nimport subprocess\nfrom bs4 import BeautifulSoup\nfrom curl_cffi import requests\nca = Path(subprocess.check_output(['mkcert', '-CAROOT'], text=True).strip()) / 'rootCA.pem'\nr = requests.get('${url}', impersonate='chrome', verify=str(ca))\nsoup = BeautifulSoup(r.text, 'html.parser')\nprint(r.status_code, [row.get_text(' ', strip=True) for row in soup.select('#dataset-table tbody tr')])`;
const examples={
 'basic':{cb:`curl -s ${url}`,cp:`curl -s ${url} | grep -A 30 'dataset-table'`,pb:staticParser,pp:staticParser},
 'rate-limit':{cb:`curl -c cookies.txt ${url}\ncurl -b cookies.txt ${origin}/rate-limit/reports/R-101\ncurl -b cookies.txt ${origin}/rate-limit/reports/R-102\ncurl -b cookies.txt ${origin}/rate-limit/reports/R-103\ncurl -b cookies.txt ${origin}/rate-limit/reports/R-104\ncurl -i -b cookies.txt ${origin}/rate-limit/reports/R-101  # 429`,cp:`curl -c cookies.txt ${url}\ncurl -b cookies.txt ${origin}/rate-limit/reports/R-101\n# Stop before the sixth request, or wait 10 seconds before continuing.`,pb:`import requests\nfrom bs4 import BeautifulSoup\ns=requests.Session()\nindex=s.get('${url}')\nsoup=BeautifulSoup(index.text,'html.parser')\nfor link in soup.select('#dataset-table a[href]'):\n    print(s.get('${origin}'+link['href']).status_code)\nprint(s.get('${origin}/rate-limit/reports/R-101').status_code)  # 429`,pp:`import time, requests\nfrom bs4 import BeautifulSoup\ns=requests.Session(); index=s.get('${url}')\nsoup=BeautifulSoup(index.text,'html.parser')\ndef get_with_backoff(href):\n    response=s.get('${origin}'+href)\n    if response.status_code == 429:\n        wait=int(response.headers['Retry-After'])\n        print(f'429: wait {wait}s, then retry {href}')\n        time.sleep(wait)\n        response=s.get('${origin}'+href)\n    return response\n# 1 index + 6 reports = 7 reads: the sixth read receives 429.\nfor href in [a['href'] for a in soup.select('#dataset-table a')]:\n    report=BeautifulSoup(get_with_backoff(href).text,'html.parser')\n    print(report.select_one('#report-details').get_text(' ',strip=True))`},
 'header-policy':{cb:`curl -i ${url}`,cp:`curl -i ${url} -H "Accept: text/html" -A "Mozilla/5.0 training-browser"`,pb:`import requests\nprint(requests.get('${url}').status_code)`,pp:`import requests\nfrom bs4 import BeautifulSoup\nr=requests.get('${url}',headers={'Accept':'text/html','User-Agent':'Mozilla/5.0 training-browser'})\nprint(r.status_code, [x.get_text(' ',strip=True) for x in BeautifulSoup(r.text,'html.parser').select('#dataset-table tbody tr')])`},
 'session-gate':{cb:`curl -i ${url}\n# 303 redirect 到登入頁，沒有 session cookie 時不提供資料表。`,cp:`curl -c cookies.txt -X POST ${origin}/session-gate/login -d "username=learner%40example.test&password=DemoPass%212026" -L\ncurl -b cookies.txt ${url}`,pb:`import requests\nr=requests.get('${url}',allow_redirects=False)\nprint(r.status_code, r.headers['Location'])  # 303 /session-gate/login`,pp:`import requests\nfrom bs4 import BeautifulSoup\ns=requests.Session()\nr=s.post('${origin}/session-gate/login',data={'username':'learner@example.test','password':'DemoPass!2026'})\nsoup=BeautifulSoup(r.text,'html.parser')\nprint(r.status_code, [x.get_text(' ',strip=True) for x in soup.select('#dataset-table tbody tr')])`},
 'deferred-content':{cb:`curl -s ${url} | grep dataset-table\n# HTML shell has no rows because curl does not execute JavaScript.`,cp:`# curl can only obtain the HTML shell; use Playwright below to obtain dynamically rendered rows.`,pb:`import requests\nfrom bs4 import BeautifulSoup\nsoup=BeautifulSoup(requests.get('${url}').text,'html.parser')\nprint(soup.select('#dataset-table tbody tr'))  # []`,pp:browserParser},
 'js-token':{cb:`curl -s ${url} | grep dataset-table\n# The token workflow is not executed.`,cp:`# Use a browser automation tool that executes this page's JavaScript.`,pb:`import requests\nfrom bs4 import BeautifulSoup\nprint(BeautifulSoup(requests.get('${url}').text,'html.parser').select('#dataset-table tbody tr'))`,pp:browserParser},
 'captcha-sim':{cb:`curl -s ${url} | grep dataset-table\n# curl cannot complete the manual verification workflow.`,cp:`# Fill in the page's verification question manually, or use Playwright below for automated testing.`,pb:`import requests\nfrom bs4 import BeautifulSoup\nprint(BeautifulSoup(requests.get('${url}').text,'html.parser').select('#dataset-table tbody tr'))`,pp:captchaParser},
 'robots-honeypot':{cb:`curl -i ${origin}/training-honeypot`,cp:`curl -i ${url}`,pb:`import requests\nprint(requests.get('${origin}/training-honeypot').status_code)`,pp:staticParser},
 'tls-fingerprint':{cb:`curl -i ${url}\n# curl 的 TLS ClientHello 不符合本機瀏覽器型態基線，因此回傳 403。`,cp:`uv run curl-cffi get ${url} --impersonate chrome --no-verify --headers`,pb:`from pathlib import Path\nimport subprocess, requests\nca=Path(subprocess.check_output(['mkcert','-CAROOT'],text=True).strip())/'rootCA.pem'\nr=requests.get('${url}',verify=ca)\nprint(r.status_code)  # 403：requests 的 OpenSSL ClientHello 不符合基線`,pp:curlCffiParser}
};
if(demo!=='basic')for(const [id,key] of Object.entries({'curl-block':'cb','curl-pass':'cp','python-block':'pb','python-pass':'pp'}))document.querySelector(`#${id}`).textContent=examples[demo][key];
const notes={
 'basic':{
  'curl-block':'本頁沒有阻擋條件。`-s`（silent）關閉 curl 的進度列，只輸出回應 HTML，方便交給後續工具或直接檢視。',
  'curl-pass':'本頁不區分阻擋與通過。`grep -A 30` 會從包含 dataset-table 的那一行起，連同後面 30 行一起輸出；它只縮小終端輸出，完全不影響 HTTP 請求。',
  'python-block':'本頁沒有阻擋條件。`requests.get()` 下載初始 HTML；Beautiful Soup 將字串解析為 DOM，`select()` 以 CSS selector 找到表格列。',
  'python-pass':'這是最小的靜態網頁抓取方式：HTTP 回應在 `r.text`，`#dataset-table tbody tr` 精確選取資料列，`get_text()` 將每列儲存格轉成可讀文字。'},
 'rate-limit':{
  'curl-block':'`-c cookies.txt` 將伺服器發出的 client cookie 寫入檔案；後續 `-b cookies.txt` 帶回同一個識別碼，才能重現同一支爬蟲連續追蹤索引與報告連結後觸發 429。最後的 `-i` 顯示 Retry-After 回應標頭。',
  'curl-pass':'先以 `-c` 儲存 cookie，再用 `-b` 存取一份詳情報告；範例刻意停在第 2 次讀取，保留配額。',
  'python-block':'`requests.Session()` 自動保存 cookie。Beautiful Soup 以 `#dataset-table a[href]` 只取報告連結，再連續請求每份報告；最後一次會印出 429。',
  'python-pass':'Beautiful Soup 的 `select("#dataset-table a")` 只取索引表內的 6 份報告連結；加上索引頁共 7 次讀取，第 6 次必定收到 429。`get_with_backoff` 會讀取 Retry-After、等待後重試，最後仍取得全部 6 份詳情表。'},
 'header-policy':{
  'curl-block':'`-i` 會連同 HTTP status 與回應標頭輸出，方便看見 403 與 X-Training-Rule；不帶額外參數的 curl 通常送出 `Accept: */*` 與 curl User-Agent，因此整個 HTML 頁面會被擋下。',
  'curl-pass':'`-H` 加入 `Accept: text/html`；`-A` 指定 User-Agent。兩者都符合本情境唯一的導覽標頭規則。',
  'python-block':'預設 `requests.get()` 不會送出此頁要求的 HTML Accept 與瀏覽器樣式 User-Agent。',
  'python-pass':'headers 字典只附上本情境要求的兩個標頭；Beautiful Soup 再從回應的整頁 HTML 選取資料列。'},
 'session-gate':{
  'curl-block':'`-i` 顯示 303、Location 與 X-Training-Rule。直接 GET 受保護頁沒有登入 session，因此會導向登入頁，資料表不會出現在回應中。',
  'curl-pass':'`-X POST` 指定表單送出方法；`-d` 送出 application/x-www-form-urlencoded 欄位（`%40` 是 @、`%21` 是 ! 的 URL 編碼）；`-c` 儲存伺服器簽發的 HttpOnly session cookie，`-L` 跟隨成功登入後的 303 redirect，最後 `-b` 再帶回 cookie。',
  'python-block':'單次 `requests.get(..., allow_redirects=False)` 沒有登入 session，會看到 303 與登入頁位置。',
  'python-pass':'同一個 `requests.Session()` 先 POST 帳密、保存回應 cookie 並跟隨 redirect，接著以 Beautiful Soup 從整頁 HTML 取得資料列。'},
 'deferred-content':{
  'curl-block':'`-s` 只輸出 HTML，管線的 `grep dataset-table` 用來確認初始文件確實有表格殼。curl 不執行 JavaScript，因此沒有任何 `<tbody>` 資料列。',
  'curl-pass':'此情境沒有單靠 curl 取得動態列的通過方式；需使用可執行頁面 JavaScript 的瀏覽器自動化工具。',
  'python-block':'Beautiful Soup 只解析 requests 已下載的初始 HTML，輸出空陣列正是此情境要驗證的結果。',
  'python-pass':'Playwright 啟動 Chromium，`goto()` 載入整頁，並以 `locator(...).wait_for()` 等待資料列由頁內 JavaScript 自動出現。'},
 'js-token':{
  'curl-block':'`-s` 只輸出初始 HTML，再由 `grep` 尋找表格元素。curl 無法執行頁內取得與使用短效 token 的 JavaScript 流程，因此初始 HTML 沒有資料列。',
  'curl-pass':'此卡片標示 curl 的限制；請使用下方 Playwright 範例，讓頁面自動取得並使用短效 token。',
  'python-block':'requests 與 Beautiful Soup 不執行 JavaScript，故只能抓到尚未解鎖的 HTML。',
  'python-pass':'Playwright 的瀏覽器環境會執行頁面腳本；等待 selector 可確定 token 驗證完成後再取表格。'},
 'captcha-sim':{
  'curl-block':'`-s` 與 `grep` 僅檢查初始 HTML 的表格殼。curl 不能顯示、填寫或提交頁面的手動驗證題目，因此不會取得資料列。',
  'curl-pass':'一般使用者在頁面輸入一次性題目的答案並按下驗證按鈕；自動化測試可使用下方 Playwright 範例填答。',
  'python-block':'requests 只能抓取文件，無法填入並送出頁面上的驗證欄位。',
  'python-pass':'Playwright 讀取驗證題目、填入答案、按下按鈕，再等待表格出現。'},
 'robots-honeypot':{
  'curl-block':'`-i` 顯示 403、X-Training-Rule 與阻擋說明。直接造訪 `/training-honeypot` 模擬爬蟲未遵守 robots.txt 中禁止路徑的情境。',
  'curl-pass':'`-i` 讓終端同時看到一般資料頁的 200 status 與標頭；此技巧的觀測點是 honeypot 路徑，而不是一般頁面。',
  'python-block':'requests 直接打 honeypot 路徑，會印出 403 以供爬蟲測試程式判斷。',
  'python-pass':'Beautiful Soup 從一般資料頁的完整 HTML 取出表格列，不會進入 honeypot。'},
 'tls-fingerprint':{
  'curl-block':'`-i` 顯示 403、X-Training-Rule 與阻擋頁。curl 已完成 HTTPS 交握，但其 ClientHello 不是 Chromium 型態；HTTP 標頭或 User-Agent 都無法改變這個交握訊號。',
  'curl-pass':'這不是原生 curl 的繞過參數，而是 curl-cffi CLI。`get` 指定 HTTP GET；`--impersonate chrome` 選用 Chrome 的 TLS／HTTP/2 型態；`--headers` 顯示回應標頭。`--no-verify` 只為 localhost mkcert 教材略過憑證驗證，正式站不可使用。',
  'python-block':'程式先由 `mkcert -CAROOT` 找到 rootCA.pem，讓 requests 在驗證憑證後真正連上網站；接著它仍因 OpenSSL ClientHello 不符合 Chromium 基線而得到 403。',
  'python-pass':'curl-cffi 以 `impersonate="chrome"` 使用 Chrome 型態的 TLS 與 HTTP/2 指紋。程式指定 mkcert 的 rootCA.pem 驗證本機憑證，通過代理判斷後，再用 Beautiful Soup 讀取整頁 HTML 中的資料列。'}
};
if(demo!=='basic')for(const [id,text] of Object.entries(notes[demo]))document.querySelector(`#${id}-note`).textContent=text;
const api=(action,body,headers={})=>fetch(`/api/${demo}/${action}`,{method:'POST',headers:{'Content-Type':'application/json',...headers},body:body?JSON.stringify(body):undefined}).then(async r=>({code:r.status,json:await r.json()}));
function renderRows(rows){const body=table.querySelector('tbody');body.replaceChildren(...rows.map(row=>{const tr=document.createElement('tr');for(const value of [row.id,row.name,row.period,row.value]){const td=document.createElement('td');td.textContent=value;tr.append(td)}return tr}));table.hidden=false;datasetState.className='verdict allowed';datasetState.textContent=`✓ 已自動載入 ${rows.length} 筆資料。`}
async function setupCaptcha(){const panel=document.querySelector('#captcha-panel'),prompt=document.querySelector('#captcha-prompt'),answer=document.querySelector('#captcha-answer'),submit=document.querySelector('#captcha-submit'),status=document.querySelector('#captcha-status');try{const issued=await api('issue');prompt.textContent=issued.json.data.prompt;panel.hidden=false;submit.onclick=async()=>{submit.disabled=true;status.textContent='正在驗證…';const response=await api('verify',{answer:answer.value});if(response.json.data?.rows){renderRows(response.json.data.rows);panel.hidden=true}else{status.textContent=`驗證失敗：${response.json.message}`;submit.disabled=false;answer.focus()}};answer.focus()}catch(error){datasetState.className='verdict blocked';datasetState.textContent=`無法準備驗證題目：${error.message}`}}
async function autoLoad(){try{if(demo==='captcha-sim'){await setupCaptcha();return}let response;if(demo==='deferred-content')response=await api('read',null,{'X-Requested-With':'XMLHttpRequest'});if(demo==='js-token'){const issued=await api('issue');response=await api('use',{token:issued.json.data.token})}if(response?.json?.data?.rows)renderRows(response.json.data.rows);else if(response)throw new Error(response.json.message)}catch(error){datasetState.className='verdict blocked';datasetState.textContent=`資料表未載入：${error.message}`}}
if(document.body.dataset.serverRows==='false')autoLoad();
