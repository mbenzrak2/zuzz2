#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ZUZZ TV v2.0 - Complete IPTV Platform with PWA, Subscriptions, Analytics, Security"""
import os,json,hashlib,secrets,re,socket,sys,threading,time,smtplib
from datetime import datetime,timedelta
from urllib.request import urlopen,Request
from functools import wraps
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

if sys.platform=='win32':
    try:sys.stdout.reconfigure(encoding='utf-8',errors='replace');sys.stderr.reconfigure(encoding='utf-8',errors='replace')
    except:pass
    os.environ['PYTHONIOENCODING']='utf-8'

def log(m):
    try:print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}")
    except:pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE','__main__')
import django
from django.conf import settings

BASE=os.path.dirname(os.path.abspath(__file__))
DATA_FILE=os.path.join(BASE,'data.json')
M3U_FILE=os.path.join(BASE,'m3u_lists.json')
ANALYTICS_FILE=os.path.join(BASE,'analytics.json')
RESET_TOKENS_FILE=os.path.join(BASE,'reset_tokens.json')

SEC={'session_hours':24,'max_attempts':5,'lockout_mins':15,'rate_limit':100,'rate_window':60}
rate_limits,login_attempts={},{}

DEFAULT_DATA={
    "users":[{"id":1,"username":"admin","password":hashlib.sha256("admin123".encode()).hexdigest(),"role":"admin","created":"2025-01-01"}],
    "viewers":[],"sessions":{},"viewer_sessions":{},
    "categories":[{"id":1,"name":"CHANNELS","icon":"📺"}],"channels":[],"subscriptions":[],
    "plans":[
        {"id":1,"name":"2-Day Pass","price":2.99,"days":2,"devices":1},
        {"id":2,"name":"Weekly Pass","price":14.99,"days":7,"devices":1},
        {"id":3,"name":"Monthly Pass","price":19.99,"days":30,"devices":1},
        {"id":4,"name":"Annual Pass","price":99.99,"original_price":240,"days":365,"devices":2,"featured":True}
    ],
    "settings":{
        "site_name":"ZUZZ TV","m3u_auto_refresh":True,"m3u_refresh_hours":6,
        "require_subscription":False,
        "paypal_app_name":"","paypal_client_id":"","paypal_secret":"",
        "smtp_host":"","smtp_port":587,"smtp_user":"","smtp_pass":"","smtp_from":"","smtp_tls":True
    }
}

# ============ SMTP EMAIL FUNCTIONS ============
def load_reset_tokens():
    try:
        with open(RESET_TOKENS_FILE,'r')as f:return json.load(f)
    except:return{}

def save_reset_tokens(t):
    with open(RESET_TOKENS_FILE,'w')as f:json.dump(t,f)

def send_email(to_email,subject,html_body):
    """Send email using SMTP settings"""
    d=load_data()
    s=d.get('settings',{})
    
    smtp_host=s.get('smtp_host','')
    smtp_port=int(s.get('smtp_port',587))
    smtp_user=s.get('smtp_user','')
    smtp_pass=s.get('smtp_pass','')
    smtp_from=s.get('smtp_from','')or smtp_user
    smtp_tls=s.get('smtp_tls',True)
    
    if not smtp_host or not smtp_user:
        log(f"[SMTP] Not configured - host:{smtp_host}, user:{smtp_user}")
        return False
    
    if not smtp_pass:
        log(f"[SMTP] Password is empty!")
        return False
    
    try:
        log(f"[SMTP] Connecting to {smtp_host}:{smtp_port} (TLS:{smtp_tls})")
        
        msg=MIMEMultipart('alternative')
        msg['Subject']=subject
        msg['From']=smtp_from
        msg['To']=to_email
        msg.attach(MIMEText(html_body,'html'))
        
        if smtp_tls:
            # Port 587 with STARTTLS
            server=smtplib.SMTP(smtp_host,smtp_port,timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            # Port 465 with SSL
            server=smtplib.SMTP_SSL(smtp_host,smtp_port,timeout=30)
        
        log(f"[SMTP] Logging in as {smtp_user}")
        server.login(smtp_user,smtp_pass)
        
        log(f"[SMTP] Sending email to {to_email}")
        server.sendmail(smtp_from,to_email,msg.as_string())
        server.quit()
        
        log(f"[SMTP] ✅ Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        log(f"[SMTP] ❌ Authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        log(f"[SMTP] ❌ SMTP Error: {e}")
        return False
    except Exception as e:
        log(f"[SMTP] ❌ Error: {type(e).__name__}: {e}")
        return False

def send_new_password_email(email,new_password,site_url):
    """Send new password email"""
    d=load_data()
    site_name=d.get('settings',{}).get('site_name','ZUZZ TV')
    
    html=f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#0d1117;color:#f0f6fc;">
        <h2 style="color:#ff5722;">🔐 {site_name} - Your New Password</h2>
        <p>Your password has been reset. Here is your new password:</p>
        <div style="background:#161b22;padding:20px;border-radius:10px;margin:20px 0;text-align:center;">
            <p style="font-size:24px;font-weight:bold;color:#ff5722;letter-spacing:2px;margin:0;">{new_password}</p>
        </div>
        <p>Please login with this password and change it immediately for security.</p>
        <p style="text-align:center;margin:30px 0;">
            <a href="{site_url}/login" style="background:linear-gradient(135deg,#ff5722,#ff9800);color:#fff;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold;">Login Now</a>
        </p>
        <hr style="border:none;border-top:1px solid #30363d;margin:20px 0;">
        <p style="color:#8b949e;font-size:12px;">If you didn't request this, please contact support immediately.</p>
        <p style="color:#8b949e;font-size:11px;">© {site_name}</p>
    </div>
    """
    return send_email(email,f"{site_name} - Your New Password",html)

def generate_password(length=10):
    """Generate random password"""
    import string
    chars=string.ascii_letters+string.digits+'!@#$%'
    return ''.join(secrets.choice(chars)for _ in range(length))

def load_data():
    try:
        with open(DATA_FILE,'r',encoding='utf-8')as f:d=json.load(f)
        for k in DEFAULT_DATA:
            if k not in d:d[k]=DEFAULT_DATA[k]
        return d
    except:import copy;return copy.deepcopy(DEFAULT_DATA)

def save_data(d):
    try:
        with open(DATA_FILE,'w',encoding='utf-8')as f:
            json.dump(d,f,ensure_ascii=False,indent=2)
        log(f"[DB] Data saved successfully")
    except Exception as e:
        log(f"[DB] ERROR saving data: {e}")
        raise e

def load_m3u():
    try:
        with open(M3U_FILE,'r',encoding='utf-8')as f:return json.load(f)
    except:return{"lists":[]}

def save_m3u(d):
    with open(M3U_FILE,'w',encoding='utf-8')as f:json.dump(d,f,ensure_ascii=False,indent=2)

def load_analytics():
    try:
        with open(ANALYTICS_FILE,'r',encoding='utf-8')as f:return json.load(f)
    except:return{"views":[],"daily":{},"popular":{}}

def save_analytics(d):
    with open(ANALYTICS_FILE,'w',encoding='utf-8')as f:json.dump(d,f,ensure_ascii=False,indent=2)

def check_rate(ip):
    now=time.time()
    if ip in rate_limits:
        r,s=rate_limits[ip]
        if now-s>SEC['rate_window']:rate_limits[ip]=(1,now);return True
        if r>=SEC['rate_limit']:return False
        rate_limits[ip]=(r+1,s)
    else:rate_limits[ip]=(1,now)
    return True

def check_attempts(ip):
    now=time.time()
    if ip in login_attempts:
        a,l=login_attempts[ip]
        if l and now<l:return False,int(l-now)
        if l and now>=l:login_attempts[ip]=(0,None)
    return True,0

def record_attempt(ip,ok):
    if ok:login_attempts[ip]=(0,None)
    else:
        a=login_attempts.get(ip,(0,None))[0]+1
        if a>=SEC['max_attempts']:login_attempts[ip]=(a,time.time()+SEC['lockout_mins']*60)
        else:login_attempts[ip]=(a,None)

def download_m3u(url):
    import ssl
    log(f"Processing:{url[:60]}...")
    m=re.search(r'(https?://[^/]+)/.*username=([^&]+).*password=([^&]+)',url)
    if m:return fetch_xtream(m.group(1),m.group(2),m.group(3))
    return download_regular(url)

def fetch_xtream(host,user,pwd):
    import ssl
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    h={'User-Agent':'IPTVSmarters'}
    try:
        r=urlopen(Request(f"{host}/player_api.php?username={user}&password={pwd}&action=get_live_categories",headers=h),timeout=60,context=ctx)
        cats=json.loads(r.read().decode('utf-8'))
        cm={str(c.get('category_id')):c.get('category_name','Other')for c in cats}
    except:cm={}
    r=urlopen(Request(f"{host}/player_api.php?username={user}&password={pwd}&action=get_live_streams",headers=h),timeout=120,context=ctx)
    chs=json.loads(r.read().decode('utf-8'))
    lines=["#EXTM3U"]
    for c in chs:
        n,s,l,g=c.get('name','?'),c.get('stream_id'),c.get('stream_icon',''),cm.get(str(c.get('category_id','')),'Other')
        lines.append(f'#EXTINF:-1 tvg-logo="{l}" group-title="{g}",{n}')
        lines.append(f'{host}/live/{user}/{pwd}/{s}.m3u8')
    return'\n'.join(lines)

def download_regular(url):
    import ssl
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    r=urlopen(Request(url,headers={'User-Agent':'VLC/3.0.18','Accept':'*/*'}),timeout=600,context=ctx)
    d=b''
    while True:
        c=r.read(1024*1024)
        if not c:break
        d+=c
    return d.decode('utf-8',errors='ignore')

def parse_m3u(content):
    chs,cats=[],set()
    lines=content.replace('\r','').split('\n')
    i=0
    while i<len(lines):
        if lines[i].startswith('#EXTINF'):
            url=lines[i+1].strip()if i+1<len(lines)else''
            if url and not url.startswith('#'):
                line=lines[i]
                m=re.search(r'tvg-name="([^"]*)"',line)
                name=m.group(1)if m else''
                if not name:m=re.search(r',([^,]+)$',line);name=m.group(1).strip()if m else f'Ch{len(chs)}'
                m=re.search(r'group-title="([^"]*)"',line);group=m.group(1)if m else'Other'
                m=re.search(r'tvg-logo="([^"]*)"',line);logo=m.group(1)if m else''
                chs.append({'name':name,'group':group,'url':url,'logo':logo})
                cats.add(group)
            i+=2
        else:i+=1
    return chs,sorted(cats)

class Scheduler:
    def __init__(self):self.running=False
    def start(self):
        if self.running:return
        self.running=True
        threading.Thread(target=self._run,daemon=True).start()
        log("[SCHEDULER] Started")
    def _run(self):
        while self.running:
            try:
                d=load_data()
                if d.get('settings',{}).get('m3u_auto_refresh',True):
                    self._refresh(d.get('settings',{}).get('m3u_refresh_hours',6))
                time.sleep(3600)
            except Exception as e:log(f"[SCHEDULER]{e}");time.sleep(300)
    def _refresh(self,hrs):
        m=load_m3u();now=datetime.now()
        for l in m.get('lists',[]):
            try:
                last=l.get('updated')or l.get('created','')
                if last and(now-datetime.strptime(last,'%Y-%m-%d %H:%M')).total_seconds()/3600>=hrs:
                    log(f"[SCHEDULER] Refreshing:{l['name']}")
                    content=download_m3u(l['url']);chs,cats=parse_m3u(content)
                    l.update({'channels':chs,'categories':cats,'channels_count':len(chs),'updated':now.strftime('%Y-%m-%d %H:%M')})
                    save_m3u(m)
            except Exception as e:log(f"[SCHEDULER] Failed:{e}")

scheduler=Scheduler()

if not settings.configured:
    settings.configure(DEBUG=True,SECRET_KEY=secrets.token_hex(32),ROOT_URLCONF=__name__,ALLOWED_HOSTS=['*'],
        INSTALLED_APPS=['django.contrib.contenttypes','django.contrib.auth'],
        MIDDLEWARE=['django.middleware.common.CommonMiddleware'],
        DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}})
django.setup()

from django.http import JsonResponse,HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import path

def get_ip(r):xff=r.META.get('HTTP_X_FORWARDED_FOR');return xff.split(',')[0]if xff else r.META.get('REMOTE_ADDR','0.0.0.0')

def verify_admin(r):
    auth=r.headers.get('Authorization','')
    if auth.startswith('Bearer '):
        d=load_data();s=d.get('sessions',{}).get(auth[7:])
        if s and datetime.now()-datetime.fromisoformat(s.get('created',datetime.now().isoformat()))<timedelta(hours=SEC['session_hours']):return s
    return None

def verify_viewer(r):
    auth=r.headers.get('Authorization','')
    if auth.startswith('Bearer '):
        d=load_data();s=d.get('viewer_sessions',{}).get(auth[7:])
        if s and datetime.now()-datetime.fromisoformat(s.get('created',datetime.now().isoformat()))<timedelta(hours=SEC['session_hours']):return s
    return None

def track_view(ch_id,ch_name,uid=None):
    a=load_analytics();today=datetime.now().strftime('%Y-%m-%d')
    a['views'].append({'ch':ch_id,'name':ch_name,'user':uid,'time':datetime.now().isoformat()})
    a['views']=a['views'][-10000:]
    if today not in a.get('daily',{}):a['daily'][today]={'views':0,'users':[]}
    a['daily'][today]['views']+=1
    if uid and uid not in a['daily'][today]['users']:a['daily'][today]['users'].append(uid)
    k=str(ch_id)
    if k not in a.get('popular',{}):a['popular'][k]={'name':ch_name,'views':0}
    a['popular'][k]['views']+=1
    save_analytics(a)

def serve_html(name):
    p=os.path.join(BASE,name)
    if os.path.exists(p):
        with open(p,'r',encoding='utf-8')as f:return HttpResponse(f.read(),content_type='text/html;charset=utf-8')
    return HttpResponse('Not found',status=404)

def home(r):return serve_html('main.html')
def admin_login(r):return serve_html('login.html')
def admin_dash(r):return serve_html('admin.html')
def m3u_page(r):return serve_html('m3u.html')
def import_events_page(r):return serve_html('import_events.html')
def m3u_player(r,list_id):
    p=os.path.join(BASE,'player.html')
    if os.path.exists(p):
        with open(p,'r',encoding='utf-8')as f:return HttpResponse(f.read().replace('LIST_ID_HERE',str(list_id)),content_type='text/html;charset=utf-8')
    return HttpResponse('Not found',status=404)
def viewer_login_page(r):return serve_html('viewer_login.html')
def viewer_register_page(r):return serve_html('viewer_register.html')
def welcome_page(r):return serve_html('welcome.html')
def payment_page(r):return serve_html('payment.html')

def manifest(r):return JsonResponse({"name":"ZUZZ TV","short_name":"ZUZZ","start_url":"/","display":"standalone","background_color":"#0d1117","theme_color":"#ff5722","icons":[{"src":"/icon-192.png","sizes":"192x192","type":"image/png"},{"src":"/icon-512.png","sizes":"512x512","type":"image/png"}]})
def sw(r):return HttpResponse("const C='zuzz-v1';self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['/']))));self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));});",content_type='application/javascript')
def icon_192(r):return HttpResponse('<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192"><rect width="192" height="192" fill="#0d1117"/><text x="96" y="110" font-size="48" font-weight="bold" fill="#ff5722" text-anchor="middle">ZUZZ</text><text x="96" y="145" font-size="24" fill="#ff9800" text-anchor="middle">TV</text></svg>',content_type='image/svg+xml')
def icon_512(r):return HttpResponse('<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="512" height="512" fill="#0d1117"/><text x="256" y="280" font-size="120" font-weight="bold" fill="#ff5722" text-anchor="middle">ZUZZ</text><text x="256" y="380" font-size="60" fill="#ff9800" text-anchor="middle">TV</text></svg>',content_type='image/svg+xml')

@csrf_exempt
def api_login(r):
    if r.method=='POST':
        ip=get_ip(r)
        if not check_rate(ip):return JsonResponse({'success':False,'error':'Rate limited'},status=429)
        ok,wait=check_attempts(ip)
        if not ok:return JsonResponse({'success':False,'error':f'Locked {wait}s'},status=429)
        try:
            b=json.loads(r.body);d=load_data();h=hashlib.sha256(b.get('password','').encode()).hexdigest()
            for u in d.get('users',[]):
                if u['username']==b.get('username')and u['password']==h:
                    t=secrets.token_hex(32)
                    d['sessions'][t]={'user_id':u['id'],'username':u['username'],'role':u.get('role','editor'),'created':datetime.now().isoformat(),'ip':ip}
                    save_data(d);record_attempt(ip,True);log(f"[AUTH] Admin:{u['username']}")
                    return JsonResponse({'success':True,'token':t,'username':u['username'],'role':u.get('role')})
            record_attempt(ip,False);return JsonResponse({'success':False,'error':'Invalid credentials'})
        except Exception as e:return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_viewer_register(r):
    if r.method=='POST':
        ip=get_ip(r)
        if not check_rate(ip):return JsonResponse({'success':False,'error':'Rate limited'},status=429)
        try:
            b=json.loads(r.body)
            user=b.get('username','').strip()
            email=b.get('email','').strip().lower()
            pwd=b.get('password','')
            
            log(f"[REGISTER] Attempting: {user}, {email}")
            
            if not user or len(user)<3:return JsonResponse({'success':False,'error':'Username min 3 chars'})
            if not email or'@'not in email:return JsonResponse({'success':False,'error':'Invalid email'})
            if len(pwd)<6:return JsonResponse({'success':False,'error':'Password min 6 chars'})
            
            d=load_data()
            for v in d.get('viewers',[]):
                if v['username'].lower()==user.lower():return JsonResponse({'success':False,'error':'Username exists'})
                if v['email']==email:return JsonResponse({'success':False,'error':'Email registered'})
            
            vid=max([v['id']for v in d.get('viewers',[])],default=0)+1
            hashed_pwd=hashlib.sha256(pwd.encode()).hexdigest()
            
            new_viewer={
                'id':vid,
                'username':user,
                'email':email,
                'password':hashed_pwd,
                'created':datetime.now().strftime('%Y-%m-%d'),
                'subscription':None,
                'favorites':[]
            }
            
            if 'viewers' not in d:
                d['viewers']=[]
            d['viewers'].append(new_viewer)
            
            t=secrets.token_hex(32)
            if 'viewer_sessions' not in d:
                d['viewer_sessions']={}
            d['viewer_sessions'][t]={'viewer_id':vid,'username':user,'created':datetime.now().isoformat()}
            
            save_data(d)
            log(f"[REGISTER] Success: {user} (ID:{vid})")
            
            # Verify save
            d2=load_data()
            log(f"[REGISTER] Verify: {len(d2.get('viewers',[]))} viewers in DB")
            
            return JsonResponse({'success':True,'token':t,'username':user,'viewer_id':vid})
        except Exception as e:
            log(f"[REGISTER] Error: {e}")
            return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_viewer_login(r):
    if r.method=='POST':
        ip=get_ip(r)
        if not check_rate(ip):return JsonResponse({'success':False,'error':'Rate limited'},status=429)
        ok,wait=check_attempts(ip)
        if not ok:return JsonResponse({'success':False,'error':f'Wait {wait}s'},status=429)
        try:
            b=json.loads(r.body)
            login=b.get('login','').strip().lower()
            pwd=b.get('password','')
            
            log(f"[LOGIN] Attempting: {login}")
            
            d=load_data()
            h=hashlib.sha256(pwd.encode()).hexdigest()
            
            log(f"[LOGIN] Viewers in DB: {len(d.get('viewers',[]))}")
            
            for v in d.get('viewers',[]):
                log(f"[LOGIN] Checking: {v['username']} / {v['email']}")
                if(v['username'].lower()==login or v['email']==login):
                    if v['password']==h:
                        t=secrets.token_hex(32)
                        if 'viewer_sessions' not in d:
                            d['viewer_sessions']={}
                        d['viewer_sessions'][t]={'viewer_id':v['id'],'username':v['username'],'created':datetime.now().isoformat()}
                        save_data(d)
                        record_attempt(ip,True)
                        sub=None
                        if v.get('subscription'):
                            exp=datetime.fromisoformat(v['subscription']['expires'])
                            if exp>datetime.now():sub=v['subscription']
                        log(f"[LOGIN] Success: {v['username']}")
                        return JsonResponse({'success':True,'token':t,'username':v['username'],'viewer_id':v['id'],'subscription':sub})
                    else:
                        log(f"[LOGIN] Password mismatch for {v['username']}")
            
            record_attempt(ip,False)
            log(f"[LOGIN] Failed: {login} not found")
            return JsonResponse({'success':False,'error':'Invalid credentials'})
        except Exception as e:
            log(f"[LOGIN] Error: {e}")
            return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_viewer_logout(r):
    auth=r.headers.get('Authorization','')
    if auth.startswith('Bearer '):
        d=load_data()
        if auth[7:]in d.get('viewer_sessions',{}):del d['viewer_sessions'][auth[7:]];save_data(d)
    return JsonResponse({'success':True})

# ============ PASSWORD RESET SYSTEM ============
def load_reset_tokens():
    """Load reset tokens from file"""
    try:
        if os.path.exists(RESET_TOKENS_FILE):
            with open(RESET_TOKENS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_reset_tokens(tokens):
    """Save reset tokens to file"""
    try:
        with open(RESET_TOKENS_FILE, 'w') as f:
            json.dump(tokens, f)
    except Exception as e:
        log(f"[RESET] Error saving tokens: {e}")

def generate_code():
    """Generate 6-digit verification code"""
    import random
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_reset_email(email, code):
    """Send password reset code via email"""
    d = load_data()
    settings = d.get('settings', {})
    
    smtp_host = settings.get('smtp_host', '')
    smtp_port = settings.get('smtp_port', 587)
    smtp_user = settings.get('smtp_user', '')
    smtp_pass = settings.get('smtp_pass', '')
    smtp_from = settings.get('smtp_from', '') or smtp_user
    smtp_tls = settings.get('smtp_tls', True)
    site_name = settings.get('site_name', 'ZUZZ TV')
    
    if not smtp_host or not smtp_user or not smtp_pass:
        log("[RESET] SMTP not configured")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🔐 {site_name} - Password Reset Code'
        msg['From'] = smtp_from
        msg['To'] = email
        
        # HTML email content
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background: #0d1117; color: #f0f6fc; padding: 20px; }}
                .container {{ max-width: 500px; margin: 0 auto; background: #161b22; border-radius: 12px; padding: 30px; }}
                .logo {{ font-size: 28px; font-weight: bold; color: #ff5722; text-align: center; margin-bottom: 20px; }}
                .code {{ font-size: 36px; font-weight: bold; letter-spacing: 8px; text-align: center; background: #0d1117; padding: 20px; border-radius: 8px; color: #ff5722; margin: 20px 0; }}
                .text {{ color: #8b949e; font-size: 14px; line-height: 1.6; }}
                .warning {{ color: #f85149; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">{site_name}</div>
                <p class="text">You requested a password reset. Use this verification code:</p>
                <div class="code">{code}</div>
                <p class="text">This code expires in <strong>10 minutes</strong>.</p>
                <p class="warning">⚠️ If you didn't request this, ignore this email.</p>
            </div>
        </body>
        </html>
        """
        
        text = f"Your {site_name} password reset code is: {code}\n\nThis code expires in 10 minutes."
        
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        if smtp_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        
        log(f"[RESET] Sent reset code to {email}")
        return True
    except Exception as e:
        log(f"[RESET] Email error: {e}")
        return False

@csrf_exempt
def api_forgot_password(r):
    """Step 1: Send verification code to email"""
    if r.method != 'POST':
        return JsonResponse({'error': 'POST only'})
    
    try:
        b = json.loads(r.body)
        email = b.get('email', '').strip().lower()
        
        if not email or '@' not in email:
            return JsonResponse({'success': False, 'error': 'Invalid email address'})
        
        # Check if email exists
        d = load_data()
        viewer = next((v for v in d.get('viewers', []) if v.get('email', '').lower() == email), None)
        
        if not viewer:
            # Don't reveal if email exists or not for security
            # But still return success (just don't send email)
            log(f"[RESET] Email not found: {email}")
            return JsonResponse({'success': False, 'error': 'Email not found in our system'})
        
        # Generate code
        code = generate_code()
        
        # Store token with expiry (10 minutes)
        tokens = load_reset_tokens()
        tokens[email] = {
            'code': code,
            'expires': (datetime.now() + timedelta(minutes=10)).isoformat(),
            'attempts': 0
        }
        save_reset_tokens(tokens)
        
        # Send email
        if send_reset_email(email, code):
            return JsonResponse({'success': True, 'message': 'Code sent'})
        else:
            return JsonResponse({'success': False, 'error': 'Failed to send email. Check SMTP settings.'})
        
    except Exception as e:
        log(f"[RESET] Error: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'})

@csrf_exempt
def api_verify_reset_code(r):
    """Step 2: Verify the 6-digit code"""
    if r.method != 'POST':
        return JsonResponse({'error': 'POST only'})
    
    try:
        b = json.loads(r.body)
        email = b.get('email', '').strip().lower()
        code = b.get('code', '').strip()
        
        tokens = load_reset_tokens()
        token_data = tokens.get(email)
        
        if not token_data:
            return JsonResponse({'success': False, 'error': 'No reset request found. Please request a new code.'})
        
        # Check expiry
        expires = datetime.fromisoformat(token_data['expires'])
        if datetime.now() > expires:
            del tokens[email]
            save_reset_tokens(tokens)
            return JsonResponse({'success': False, 'error': 'Code expired. Please request a new one.'})
        
        # Check attempts
        if token_data.get('attempts', 0) >= 5:
            del tokens[email]
            save_reset_tokens(tokens)
            return JsonResponse({'success': False, 'error': 'Too many attempts. Please request a new code.'})
        
        # Verify code
        if code != token_data['code']:
            token_data['attempts'] = token_data.get('attempts', 0) + 1
            save_reset_tokens(tokens)
            return JsonResponse({'success': False, 'error': 'Invalid code. Please try again.'})
        
        # Code is valid - generate reset token
        reset_token = secrets.token_hex(32)
        token_data['verified'] = True
        token_data['reset_token'] = reset_token
        token_data['token_expires'] = (datetime.now() + timedelta(minutes=15)).isoformat()
        save_reset_tokens(tokens)
        
        log(f"[RESET] Code verified for {email}")
        return JsonResponse({'success': True, 'token': reset_token})
        
    except Exception as e:
        log(f"[RESET] Verify error: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'})

@csrf_exempt
def api_reset_password(r):
    """Step 3: Set new password"""
    if r.method != 'POST':
        return JsonResponse({'error': 'POST only'})
    
    try:
        b = json.loads(r.body)
        email = b.get('email', '').strip().lower()
        reset_token = b.get('token', '')
        password = b.get('password', '')
        
        if len(password) < 6:
            return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters'})
        
        tokens = load_reset_tokens()
        token_data = tokens.get(email)
        
        if not token_data or not token_data.get('verified'):
            return JsonResponse({'success': False, 'error': 'Invalid reset session'})
        
        if token_data.get('reset_token') != reset_token:
            return JsonResponse({'success': False, 'error': 'Invalid token'})
        
        # Check token expiry
        token_expires = datetime.fromisoformat(token_data.get('token_expires', '2000-01-01'))
        if datetime.now() > token_expires:
            del tokens[email]
            save_reset_tokens(tokens)
            return JsonResponse({'success': False, 'error': 'Session expired. Please start over.'})
        
        # Update password
        d = load_data()
        for v in d.get('viewers', []):
            if v.get('email', '').lower() == email:
                v['password'] = hashlib.sha256(password.encode()).hexdigest()
                break
        save_data(d)
        
        # Clean up token
        del tokens[email]
        save_reset_tokens(tokens)
        
        log(f"[RESET] Password reset successful for {email}")
        return JsonResponse({'success': True})
        
    except Exception as e:
        log(f"[RESET] Reset error: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'})
# ============ END PASSWORD RESET ============

@csrf_exempt
def api_viewer_delete(r):
    """Delete a viewer (admin only)"""
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
        try:
            b=json.loads(r.body)
            vid=b.get('id')
            d=load_data()
            # Remove viewer
            d['viewers']=[v for v in d.get('viewers',[]) if v['id']!=vid]
            # Remove their sessions
            d['viewer_sessions']={k:v for k,v in d.get('viewer_sessions',{}).items() if v.get('viewer_id')!=vid}
            save_data(d)
            log(f"[ADMIN] Deleted viewer ID: {vid}")
            return JsonResponse({'success':True})
        except Exception as e:
            return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_viewer_manage(r):
    """Add or edit viewer (admin only)"""
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
        try:
            b=json.loads(r.body)
            vid=b.get('id')
            username=b.get('username','').strip()
            email=b.get('email','').strip().lower()
            password=b.get('password','')
            plan_id=b.get('plan_id')
            
            if not username or len(username)<3:
                return JsonResponse({'success':False,'error':'Username min 3 chars'})
            if not email or '@' not in email:
                return JsonResponse({'success':False,'error':'Invalid email'})
            
            d=load_data()
            
            if vid:
                # Edit existing viewer
                viewer=next((v for v in d.get('viewers',[]) if v['id']==vid),None)
                if not viewer:
                    return JsonResponse({'success':False,'error':'Viewer not found'})
                
                # Check username/email not taken by others
                for v in d.get('viewers',[]):
                    if v['id']!=vid:
                        if v['username'].lower()==username.lower():
                            return JsonResponse({'success':False,'error':'Username exists'})
                        if v['email']==email:
                            return JsonResponse({'success':False,'error':'Email exists'})
                
                viewer['username']=username
                viewer['email']=email
                if password and len(password)>=6:
                    viewer['password']=hashlib.sha256(password.encode()).hexdigest()
                
                # Update subscription if plan selected
                if plan_id:
                    plan=next((p for p in d.get('plans',[]) if p['id']==plan_id),None)
                    if plan:
                        exp=datetime.now()+timedelta(days=plan['days'])
                        viewer['subscription']={
                            'plan_id':plan['id'],
                            'plan_name':plan['name'],
                            'price':plan['price'],
                            'devices':plan.get('devices',1),
                            'started':datetime.now().isoformat(),
                            'expires':exp.isoformat()
                        }
                
                log(f"[ADMIN] Updated viewer: {username}")
            else:
                # Add new viewer
                if not password or len(password)<6:
                    return JsonResponse({'success':False,'error':'Password min 6 chars'})
                
                # Check username/email not taken
                for v in d.get('viewers',[]):
                    if v['username'].lower()==username.lower():
                        return JsonResponse({'success':False,'error':'Username exists'})
                    if v['email']==email:
                        return JsonResponse({'success':False,'error':'Email exists'})
                
                new_id=max([v['id'] for v in d.get('viewers',[])],default=0)+1
                new_viewer={
                    'id':new_id,
                    'username':username,
                    'email':email,
                    'password':hashlib.sha256(password.encode()).hexdigest(),
                    'created':datetime.now().strftime('%Y-%m-%d'),
                    'subscription':None,
                    'favorites':[]
                }
                
                if 'viewers' not in d:
                    d['viewers']=[]
                d['viewers'].append(new_viewer)
                log(f"[ADMIN] Created viewer: {username} (ID:{new_id})")
            
            save_data(d)
            return JsonResponse({'success':True})
        except Exception as e:
            log(f"[ADMIN] Viewer manage error: {e}")
            return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_viewer_profile(r):
    s=verify_viewer(r)
    if not s:return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
    d=load_data();v=next((x for x in d.get('viewers',[])if x['id']==s['viewer_id']),None)
    if not v:return JsonResponse({'success':False,'error':'Not found'})
    if r.method=='GET':
        sub=None
        if v.get('subscription'):
            exp=datetime.fromisoformat(v['subscription']['expires'])
            if exp>datetime.now():sub=v['subscription'].copy();sub['days_left']=(exp-datetime.now()).days
        return JsonResponse({'success':True,'viewer':{'id':v['id'],'username':v['username'],'email':v['email'],'created':v['created'],'subscription':sub,'favorites':v.get('favorites',[])}})
    elif r.method=='POST':
        b=json.loads(r.body)
        if b.get('email'):v['email']=b['email'].lower()
        if b.get('password')and len(b['password'])>=6:v['password']=hashlib.sha256(b['password'].encode()).hexdigest()
        save_data(d);return JsonResponse({'success':True})
    return JsonResponse({'error':'Method not allowed'})

@csrf_exempt
def api_favorites(r):
    s=verify_viewer(r)
    if not s:return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
    d=load_data();v=next((x for x in d.get('viewers',[])if x['id']==s['viewer_id']),None)
    if not v:return JsonResponse({'success':False,'error':'Not found'})
    if r.method=='GET':return JsonResponse({'success':True,'favorites':v.get('favorites',[])})
    elif r.method=='POST':
        b=json.loads(r.body);action,ch_id=b.get('action'),b.get('channel_id');favs=v.get('favorites',[])
        if action=='add'and ch_id not in favs:favs.append(ch_id)
        elif action=='remove'and ch_id in favs:favs.remove(ch_id)
        elif action=='toggle':favs.remove(ch_id)if ch_id in favs else favs.append(ch_id)
        v['favorites']=favs;save_data(d);return JsonResponse({'success':True,'favorites':favs})
    return JsonResponse({'error':'Method not allowed'})

@csrf_exempt
def api_plans(r):
    d=load_data()
    return JsonResponse({
        'success':True,
        'plans':d.get('plans',DEFAULT_DATA['plans']),
        'paypal_client_id':d.get('settings',{}).get('paypal_client_id','')
    })

@csrf_exempt
def api_plan(r):
    """Add or update a plan (admin only)"""
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
        try:
            b=json.loads(r.body)
            d=load_data()
            
            plan_id=b.get('id')
            name=b.get('name','').strip()
            days=int(b.get('days',0))
            price=float(b.get('price',0))
            devices=int(b.get('devices',1))
            original_price=b.get('original_price')
            featured=b.get('featured',False)
            
            if not name:return JsonResponse({'success':False,'error':'Name required'})
            if days<1:return JsonResponse({'success':False,'error':'Days must be at least 1'})
            if price<0:return JsonResponse({'success':False,'error':'Invalid price'})
            
            if 'plans' not in d:
                d['plans']=[]
            
            if plan_id:
                # Update existing
                for p in d['plans']:
                    if p['id']==plan_id:
                        p['name']=name
                        p['days']=days
                        p['price']=price
                        p['devices']=devices
                        p['featured']=featured
                        if original_price:
                            p['original_price']=float(original_price)
                        elif 'original_price' in p:
                            del p['original_price']
                        break
                log(f"[ADMIN] Updated plan: {name}")
            else:
                # Add new
                new_id=max([p['id'] for p in d['plans']],default=0)+1
                new_plan={'id':new_id,'name':name,'days':days,'price':price,'devices':devices,'featured':featured}
                if original_price:
                    new_plan['original_price']=float(original_price)
                d['plans'].append(new_plan)
                log(f"[ADMIN] Created plan: {name} (ID:{new_id})")
            
            save_data(d)
            return JsonResponse({'success':True})
        except Exception as e:
            return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_plan_delete(r):
    """Delete a plan (admin only)"""
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
        try:
            b=json.loads(r.body)
            plan_id=b.get('id')
            d=load_data()
            d['plans']=[p for p in d.get('plans',[]) if p['id']!=plan_id]
            save_data(d)
            log(f"[ADMIN] Deleted plan ID: {plan_id}")
            return JsonResponse({'success':True})
        except Exception as e:
            return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_subscribe(r):
    if r.method=='POST':
        s=verify_viewer(r)
        if not s:return JsonResponse({'success':False,'error':'Login first'},status=401)
        try:
            b=json.loads(r.body);plan_id,order_id=b.get('plan_id'),b.get('paypal_order_id');d=load_data()
            plan=next((p for p in d.get('plans',[])if p['id']==plan_id),None)
            if not plan:return JsonResponse({'success':False,'error':'Plan not found'})
            v=next((x for x in d.get('viewers',[])if x['id']==s['viewer_id']),None)
            if not v:return JsonResponse({'success':False,'error':'Viewer not found'})
            exp=datetime.now()+timedelta(days=plan['days'])
            v['subscription']={'plan_id':plan['id'],'plan_name':plan['name'],'price':plan['price'],'devices':plan.get('devices',1),'started':datetime.now().isoformat(),'expires':exp.isoformat(),'paypal_order_id':order_id}
            d.setdefault('subscriptions',[]).append({'id':len(d.get('subscriptions',[]))+1,'viewer_id':v['id'],'viewer':v['username'],'plan':plan['name'],'price':plan['price'],'paypal':order_id,'created':datetime.now().isoformat()})
            save_data(d);log(f"[SUB]{v['username']}->{plan['name']}")
            return JsonResponse({'success':True,'subscription':v['subscription']})
        except Exception as e:return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_data(r):
    d=load_data();req_sub=d.get('settings',{}).get('require_subscription',False);vs=verify_viewer(r);has_sub=False
    if vs:
        v=next((x for x in d.get('viewers',[])if x['id']==vs['viewer_id']),None)
        if v and v.get('subscription'):
            if datetime.fromisoformat(v['subscription']['expires'])>datetime.now():has_sub=True
    chs=d.get('channels',[])
    if req_sub and not has_sub and not verify_admin(r):chs=chs[:3]
    users=[{'id':u['id'],'username':u['username'],'role':u['role'],'created':u.get('created','')}for u in d.get('users',[])]
    return JsonResponse({'categories':d.get('categories',[]),'channels':chs,'users':users,'require_subscription':req_sub,'has_subscription':has_sub})

@csrf_exempt
def api_track(r):
    if r.method=='POST':
        try:b=json.loads(r.body);vs=verify_viewer(r);track_view(b.get('channel_id'),b.get('channel_name',''),vs['viewer_id']if vs else None)
        except:pass
    return JsonResponse({'success':True})

@csrf_exempt
def api_channel(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False,'error':'Auth'})
        b=json.loads(r.body);d=load_data()
        # Support multiple servers
        servers=b.get('servers',[])
        if not servers and b.get('iframe'):servers=[b.get('iframe')]
        if b.get('id'):
            for c in d['channels']:
                if c['id']==b['id']:c.update({'name':b['name'],'servers':servers,'iframe':servers[0]if servers else'','icon':b.get('icon','📺'),'category_id':b.get('category_id',1)});break
        else:
            nid=max([c['id']for c in d['channels']],default=0)+1
            d['channels'].append({'id':nid,'name':b['name'],'servers':servers,'iframe':servers[0]if servers else'','icon':b.get('icon','📺'),'category_id':b.get('category_id',1)})
        save_data(d);return JsonResponse({'success':True})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_channel_del(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False})
        b=json.loads(r.body);d=load_data();d['channels']=[c for c in d['channels']if c['id']!=b['id']];save_data(d);return JsonResponse({'success':True})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_category(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False})
        b=json.loads(r.body);d=load_data()
        if b.get('id'):
            for c in d['categories']:
                if c['id']==b['id']:c.update({'name':b['name'],'icon':b.get('icon','🏷️')});break
        else:
            nid=max([c['id']for c in d['categories']],default=0)+1
            d['categories'].append({'id':nid,'name':b['name'],'icon':b.get('icon','🏷️')})
        save_data(d);return JsonResponse({'success':True})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_category_del(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False})
        b=json.loads(r.body);d=load_data()
        for c in d['channels']:
            if c['category_id']==b['id']:c['category_id']=1
        if b['id']!=1:d['categories']=[c for c in d['categories']if c['id']!=b['id']]
        save_data(d);return JsonResponse({'success':True})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_user(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False})
        b=json.loads(r.body);d=load_data()
        if b.get('id'):
            for u in d['users']:
                if u['id']==b['id']:u['username']=b['username'];u['role']=b.get('role','editor')
                if b.get('password'):u['password']=hashlib.sha256(b['password'].encode()).hexdigest()
                break
        else:
            if not b.get('password'):return JsonResponse({'success':False,'error':'Password required'})
            nid=max([u['id']for u in d['users']],default=0)+1
            d['users'].append({'id':nid,'username':b['username'],'password':hashlib.sha256(b['password'].encode()).hexdigest(),'role':b.get('role','editor'),'created':datetime.now().strftime('%Y-%m-%d')})
        save_data(d);return JsonResponse({'success':True})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_user_del(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False})
        b=json.loads(r.body)
        if b['id']==1:return JsonResponse({'success':False,'error':'Cannot delete admin'})
        d=load_data();d['users']=[u for u in d['users']if u['id']!=b['id']];save_data(d);return JsonResponse({'success':True})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_m3u_lists(r):m=load_m3u();return JsonResponse({'lists':[{'id':l['id'],'name':l['name'],'channels_count':l.get('channels_count',0),'created':l.get('created',''),'updated':l.get('updated','')}for l in m.get('lists',[])]})

@csrf_exempt
def api_m3u_import(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'})
        try:
            b=json.loads(r.body);url,name=b.get('url',''),b.get('name','My List')
            if not url:return JsonResponse({'success':False,'error':'URL required'})
            content=download_m3u(url);chs,cats=parse_m3u(content)
            if not chs:return JsonResponse({'success':False,'error':'No channels'})
            m=load_m3u();nid=max([l['id']for l in m.get('lists',[])],default=0)+1
            m.setdefault('lists',[]).append({'id':nid,'name':name,'url':url,'channels_count':len(chs),'categories':cats,'created':datetime.now().strftime('%Y-%m-%d %H:%M'),'channels':chs})
            save_m3u(m);return JsonResponse({'success':True,'list_id':nid,'channels_count':len(chs),'categories_count':len(cats)})
        except Exception as e:return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'POST only'})

@csrf_exempt
def api_m3u_channels(r,list_id):
    m=load_m3u()
    for l in m.get('lists',[]):
        if l['id']==int(list_id):return JsonResponse({'success':True,'list':{'id':l['id'],'name':l['name'],'categories':l.get('categories',[])},'channels':l.get('channels',[])})
    return JsonResponse({'success':False,'error':'Not found'})

@csrf_exempt
def api_m3u_del(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False})
        b=json.loads(r.body);m=load_m3u();m['lists']=[l for l in m.get('lists',[])if l['id']!=b.get('id')];save_m3u(m);return JsonResponse({'success':True})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_m3u_refresh(r):
    if r.method=='POST':
        if not verify_admin(r):return JsonResponse({'success':False})
        b=json.loads(r.body);m=load_m3u()
        for l in m.get('lists',[]):
            if l['id']==b.get('id'):
                content=download_m3u(l['url']);chs,cats=parse_m3u(content)
                l.update({'channels':chs,'categories':cats,'channels_count':len(chs),'updated':datetime.now().strftime('%Y-%m-%d %H:%M')})
                save_m3u(m);return JsonResponse({'success':True,'channels_count':len(chs)})
        return JsonResponse({'success':False,'error':'Not found'})
    return JsonResponse({'error':'POST'})

@csrf_exempt
def api_analytics(r):
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
    a=load_analytics();d=load_data();today=datetime.now().strftime('%Y-%m-%d')
    ts=a.get('daily',{}).get(today,{'views':0,'users':[]})
    pop=sorted(a.get('popular',{}).items(),key=lambda x:x[1]['views'],reverse=True)[:10]
    return JsonResponse({'success':True,'today':{'views':ts['views'],'users':len(ts.get('users',[]))},'total_viewers':len(d.get('viewers',[])),'total_subs':len([v for v in d.get('viewers',[])if v.get('subscription')]),'popular':[{'name':v['name'],'views':v['views']}for k,v in pop],'daily':a.get('daily',{})})

@csrf_exempt
def api_settings(r):
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
    d=load_data()
    if r.method=='GET':
        return JsonResponse({'success':True,'settings':d.get('settings',DEFAULT_DATA['settings'])})
    elif r.method=='POST':
        try:
            b=json.loads(r.body)
            log(f"[SETTINGS] Saving: {b}")
            s=d.get('settings',{})
            s.update(b)
            d['settings']=s
            save_data(d)
            log(f"[SETTINGS] Saved successfully. require_subscription={s.get('require_subscription')}")
            return JsonResponse({'success':True})
        except Exception as e:
            log(f"[SETTINGS] Error: {e}")
            return JsonResponse({'success':False,'error':str(e)})
    return JsonResponse({'error':'Method not allowed'})

@csrf_exempt
def api_viewers(r):
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
    d=load_data();vs=[]
    for v in d.get('viewers',[]):
        sub=None
        if v.get('subscription'):
            exp=datetime.fromisoformat(v['subscription']['expires'])
            if exp>datetime.now():sub={'plan':v['subscription']['plan_name'],'expires':v['subscription']['expires']}
        vs.append({'id':v['id'],'username':v['username'],'email':v['email'],'created':v['created'],'subscription':sub})
    return JsonResponse({'success':True,'viewers':vs,'total':len(vs)})

# ============ MATCHES SYSTEM ============
MATCHES_FILE=os.path.join(BASE,'matches.json')
UPLOADS_DIR=os.path.join(BASE,'uploads')
os.makedirs(UPLOADS_DIR,exist_ok=True)

def load_matches():
    try:
        with open(MATCHES_FILE,'r',encoding='utf-8')as f:return json.load(f)
    except:return{'matches':[]}

def save_matches(m):
    with open(MATCHES_FILE,'w',encoding='utf-8')as f:json.dump(m,f,ensure_ascii=False,indent=2)

@csrf_exempt
def api_matches(r):
    m=load_matches()
    return JsonResponse({'success':True,'matches':m.get('matches',[])})

@csrf_exempt  
def api_match_save(r):
    if r.method!='POST':return JsonResponse({'error':'POST only'})
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'})
    
    m=load_matches()
    match_id=r.POST.get('id')
    
    # Handle file uploads
    logo1_path=''
    logo2_path=''
    
    if 'logo1' in r.FILES:
        f=r.FILES['logo1']
        fname=f'logo1_{int(time.time())}_{f.name}'
        fpath=os.path.join(UPLOADS_DIR,fname)
        with open(fpath,'wb')as dest:
            for chunk in f.chunks():dest.write(chunk)
        logo1_path=f'/uploads/{fname}'
    
    if 'logo2' in r.FILES:
        f=r.FILES['logo2']
        fname=f'logo2_{int(time.time())}_{f.name}'
        fpath=os.path.join(UPLOADS_DIR,fname)
        with open(fpath,'wb')as dest:
            for chunk in f.chunks():dest.write(chunk)
        logo2_path=f'/uploads/{fname}'
    
    match_data={
        'team1':r.POST.get('team1',''),
        'team2':r.POST.get('team2',''),
        'category_id':int(r.POST.get('category_id',1)),
        'stream_url':r.POST.get('stream_url',''),
        'match_datetime':r.POST.get('match_datetime',''),
        'active':r.POST.get('active','true')=='true'
    }
    
    if match_id:
        # Update existing
        for match in m['matches']:
            if str(match['id'])==str(match_id):
                match.update(match_data)
                if logo1_path:match['logo1']=logo1_path
                if logo2_path:match['logo2']=logo2_path
                break
    else:
        # New match
        nid=max([x['id']for x in m['matches']],default=0)+1
        match_data['id']=nid
        match_data['logo1']=logo1_path
        match_data['logo2']=logo2_path
        match_data['created']=datetime.now().strftime('%Y-%m-%d %H:%M')
        m['matches'].append(match_data)
    
    save_matches(m)
    return JsonResponse({'success':True})

@csrf_exempt
def api_match_delete(r):
    if r.method!='POST':return JsonResponse({'error':'POST only'})
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'})
    b=json.loads(r.body)
    m=load_matches()
    m['matches']=[x for x in m['matches']if x['id']!=b.get('id')]
    save_matches(m)
    return JsonResponse({'success':True})

@csrf_exempt
def api_match_toggle(r):
    if r.method!='POST':return JsonResponse({'error':'POST only'})
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'})
    b=json.loads(r.body)
    m=load_matches()
    for match in m['matches']:
        if match['id']==b.get('id'):
            match['active']=b.get('active',True)
            break
    save_matches(m)
    return JsonResponse({'success':True})

# ============ SOFASCORE IMPORT ============
import urllib.request
import urllib.error

@csrf_exempt
def api_import_fetch_events(r):
    """Fetch events from SofaScore API"""
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
    
    # Get API settings
    d = load_data()
    settings = d.get('settings', {})
    api_key = settings.get('sofascore_key', '')
    api_host = settings.get('sofascore_host', 'sportapi7.p.rapidapi.com')
    
    if not api_key:
        return JsonResponse({'success': False, 'error': 'SofaScore API key not configured. Go to Settings → SofaScore API'})
    
    sport = r.GET.get('sport', 'football')
    date = r.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # Map sport names to SofaScore sport slugs
    sport_map = {
        'football': 'football',
        'basketball': 'basketball', 
        'tennis': 'tennis',
        'hockey': 'ice-hockey',
        'american-football': 'american-football',
        'baseball': 'baseball',
        'cricket': 'cricket',
        'volleyball': 'volleyball',
        'mma': 'mma',
        'motorsport': 'motorsport',
        'rugby': 'rugby',
        'aussie-rules': 'aussie-rules',
        'handball': 'handball',
        'esports': 'esports',
        'boxing': 'mma',  # Boxing is under MMA in SofaScore
        'golf': 'golf',
        'athletics': 'athletics'
    }
    
    sport_slug = sport_map.get(sport, 'football')
    
    try:
        url = f"https://{api_host}/api/v1/sport/{sport_slug}/scheduled-events/{date}"
        
        req = urllib.request.Request(url)
        req.add_header('x-rapidapi-host', api_host)
        req.add_header('x-rapidapi-key', api_key)
        
        log(f"[IMPORT] Fetching: {url}")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        
        events = []
        now = datetime.now()
        
        for event in data.get('events', []):
            try:
                home_team = event.get('homeTeam', {})
                away_team = event.get('awayTeam', {})
                tournament = event.get('tournament', {})
                
                home_id = home_team.get('id', '')
                away_id = away_team.get('id', '')
                tournament_id = tournament.get('uniqueTournament', {}).get('id', '') or tournament.get('id', '')
                
                # SofaScore gives Unix timestamp (UTC)
                start_timestamp = event.get('startTimestamp', 0)
                # Convert to UTC datetime and format as ISO with Z suffix
                if start_timestamp:
                    from datetime import timezone
                    start_time = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
                    start_time_iso = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    start_time_iso = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                
                # Determine status
                status_code = event.get('status', {}).get('type', '')
                if status_code == 'inprogress':
                    status = 'live'
                elif status_code == 'finished':
                    status = 'finished'
                else:
                    status = 'upcoming'
                
                # Skip finished matches (only show live and upcoming)
                if status == 'finished':
                    continue
                
                # Use img.sofascore.com for images (works with no-referrer)
                events.append({
                    'id': event.get('id', ''),
                    'homeTeam': home_team.get('name', 'Unknown'),
                    'awayTeam': away_team.get('name', 'Unknown'),
                    'homeId': home_id,
                    'awayId': away_id,
                    'homeLogo': f"https://img.sofascore.com/api/v1/team/{home_id}/image" if home_id else '',
                    'awayLogo': f"https://img.sofascore.com/api/v1/team/{away_id}/image" if away_id else '',
                    'league': tournament.get('name', ''),
                    'leagueId': tournament_id,
                    'leagueLogo': f"https://img.sofascore.com/api/v1/unique-tournament/{tournament_id}/image" if tournament_id else '',
                    'startTime': start_time_iso,
                    'status': status,
                    'streamUrl': ''
                })
            except Exception as e:
                log(f"[IMPORT] Error parsing event: {e}")
                continue
        
        log(f"[IMPORT] Found {len(events)} events for {sport} on {date}")
        return JsonResponse({'success': True, 'events': events})
        
    except urllib.error.HTTPError as e:
        log(f"[IMPORT] HTTP Error: {e.code} - {e.reason}")
        if e.code == 403:
            return JsonResponse({'success': False, 'error': 'API Access Denied. Check your RapidAPI key.'})
        return JsonResponse({'success': False, 'error': f'API Error: {e.code}'})
    except Exception as e:
        log(f"[IMPORT] Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def api_import_save_events(r):
    """Save imported events as matches"""
    if r.method != 'POST':
        return JsonResponse({'error': 'POST only'})
    if not verify_admin(r):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)
    
    try:
        b = json.loads(r.body)
        events = b.get('events', [])
        
        if not events:
            return JsonResponse({'success': False, 'error': 'No events to import'})
        
        m = load_matches()
        imported = 0
        
        for event in events:
            # Check if already exists (by sofascore_id)
            sofascore_id = event.get('sofascore_id', '')
            if sofascore_id:
                existing = any(
                    str(match.get('sofascore_id')) == str(sofascore_id) 
                    for match in m.get('matches', [])
                )
                if existing:
                    log(f"[IMPORT] Skipping duplicate: {event.get('team1')} vs {event.get('team2')}")
                    continue
            
            new_id = max([match['id'] for match in m.get('matches', [])], default=0) + 1
            
            # Use direct SofaScore image URLs (with no-referrer in frontend)
            home_id = event.get('homeId', '')
            away_id = event.get('awayId', '')
            league_id = event.get('leagueId', '')
            
            logo1 = f"https://img.sofascore.com/api/v1/team/{home_id}/image" if home_id else ''
            logo2 = f"https://img.sofascore.com/api/v1/team/{away_id}/image" if away_id else ''
            league_logo = f"https://img.sofascore.com/api/v1/unique-tournament/{league_id}/image" if league_id else ''
            
            new_match = {
                'id': new_id,
                'team1': event.get('team1', ''),
                'team2': event.get('team2', ''),
                'logo1': logo1,
                'logo2': logo2,
                'category_id': event.get('category_id', 1),
                'stream_url': event.get('stream_url', ''),
                'match_datetime': event.get('match_datetime', ''),
                'league': event.get('league', ''),
                'league_logo': league_logo,
                'sofascore_id': sofascore_id,
                'active': True
            }
            
            if 'matches' not in m:
                m['matches'] = []
            m['matches'].append(new_match)
            imported += 1
            log(f"[IMPORT] Added match: {event.get('team1')} vs {event.get('team2')}")
        
        save_matches(m)
        log(f"[IMPORT] Imported {imported} events total")
        
        return JsonResponse({'success': True, 'imported': imported})
        
    except Exception as e:
        log(f"[IMPORT] Save error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def api_upload_icon(r):
    """Upload icon image for category/channel"""
    if r.method!='POST':return JsonResponse({'error':'POST only'})
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'},status=401)
    
    try:
        if 'icon' not in r.FILES:
            return JsonResponse({'success':False,'error':'No file uploaded'})
        
        f=r.FILES['icon']
        icon_type=r.POST.get('type','category')
        
        # Validate file
        allowed_ext=['png','jpg','jpeg','gif','webp']
        ext=f.name.split('.')[-1].lower()
        if ext not in allowed_ext:
            return JsonResponse({'success':False,'error':'Invalid file type. Use PNG, JPG, GIF or WebP'})
        
        # Save file
        fname=f'{icon_type}_{int(time.time())}_{f.name}'
        fpath=os.path.join(UPLOADS_DIR,fname)
        
        with open(fpath,'wb') as dest:
            for chunk in f.chunks():
                dest.write(chunk)
        
        log(f"[UPLOAD] Icon saved: {fname}")
        return JsonResponse({'success':True,'path':f'/uploads/{fname}'})
    except Exception as e:
        log(f"[UPLOAD] Error: {e}")
        return JsonResponse({'success':False,'error':str(e)})

def serve_upload(r,filename):
    fpath=os.path.join(UPLOADS_DIR,filename)
    if os.path.exists(fpath):
        with open(fpath,'rb')as f:
            content=f.read()
        ext=filename.split('.')[-1].lower()
        ct={'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','gif':'image/gif','webp':'image/webp','svg':'image/svg+xml'}.get(ext,'application/octet-stream')
        return HttpResponse(content,content_type=ct)
    return HttpResponse('Not found',status=404)

# ============ PASSWORD RESET ============
@csrf_exempt
def api_test_smtp(r):
    """Test SMTP settings"""
    if not verify_admin(r):return JsonResponse({'success':False,'error':'Unauthorized'})
    if r.method!='POST':return JsonResponse({'error':'POST only'})
    try:
        b=json.loads(r.body)
        test_email=b.get('email','')
        if not test_email:return JsonResponse({'success':False,'error':'Test email required'})
        
        d=load_data()
        s=d.get('settings',{})
        site_name=s.get('site_name','ZUZZ TV')
        
        # Log SMTP settings (without password)
        log(f"[SMTP TEST] Host: {s.get('smtp_host')}, Port: {s.get('smtp_port')}, User: {s.get('smtp_user')}, TLS: {s.get('smtp_tls')}")
        log(f"[SMTP TEST] Password exists: {bool(s.get('smtp_pass'))}")
        
        html=f"""
        <div style="font-family:Arial,sans-serif;padding:20px;">
            <h2 style="color:#ff5722;">✅ {site_name} - SMTP Test</h2>
            <p>Your SMTP settings are working correctly!</p>
            <p style="color:#666;font-size:12px;">Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        """
        
        if send_email(test_email,f"{site_name} - SMTP Test",html):
            return JsonResponse({'success':True,'message':f'Test email sent to {test_email}'})
        else:
            return JsonResponse({'success':False,'error':'Failed to send. Check SMTP settings.'})
    except Exception as e:
        log(f"[SMTP TEST] Error: {e}")
        return JsonResponse({'success':False,'error':str(e)})

# ============ STATIC PAGES ============
PAGE_HEADER='''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} - ZUZZ TV</title>
<style>:root{--p:#ff5722;--bg:#0a1628;--card:#0f1f3a;--hov:#162d50;--bdr:#1e3a5f;--txt:#f0f6fc;--mut:#8b949e}*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui;background:var(--bg);color:var(--txt);min-height:100vh}
.header{display:flex;align-items:center;justify-content:space-between;padding:15px 30px;background:var(--card);border-bottom:1px solid var(--bdr)}.logo{font-size:28px;font-weight:800;color:var(--p)}.logo span{color:var(--txt);font-size:14px;margin-left:5px;background:var(--p);padding:2px 8px;border-radius:4px}
.header-center{display:flex;align-items:center;gap:15px}.time{background:var(--hov);padding:8px 15px;border-radius:20px;font-weight:600}.header-right{display:flex;gap:20px;align-items:center}.header-link{color:var(--mut);text-decoration:none;font-size:13px}.header-link:hover{color:var(--txt)}.btn-account{background:var(--p);color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px}
.main{max-width:1200px;margin:0 auto;padding:40px 20px}
.footer{background:var(--card);border-top:1px solid var(--bdr);padding:20px 30px;text-align:center}.footer-links{display:flex;justify-content:center;gap:20px;flex-wrap:wrap;margin-bottom:10px}.footer-links a{color:var(--p);text-decoration:none;font-size:13px}.footer-copy{color:var(--mut);font-size:12px}
</style></head><body>
<header class="header"><a href="/" style="text-decoration:none"><div class="logo">ZUZZ<span>TV</span></div></a><div class="header-center"><span class="time" id="time">00:00</span></div><div class="header-right"><a href="/why-zuzz" class="header-link">Why zuzz?</a><a href="/faq" class="header-link">ⓘ FAQ</a><a href="/login" class="btn-account">My Account</a></div></header>
<main class="main">'''

PAGE_FOOTER='''</main>
<footer class="footer"><div class="footer-links"><a href="/terms">Terms And Conditions</a><a href="/privacy">Privacy Policy</a><a href="/affiliates">Affiliates</a><a href="/contact">Contact Us</a></div><div class="footer-copy">COPYRIGHT © 2019-2025 - ZUZZ TV</div></footer>
<script>setInterval(()=>{document.getElementById('time').textContent=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})},1000);document.getElementById('time').textContent=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});</script>
</body></html>'''

# Helper function to serve HTML pages with dynamic site name
def serve_html_page(filename):
    """Serve HTML file with site_name replaced"""
    try:
        d = load_data()
        site_name = d.get('settings', {}).get('site_name', 'ZUZZ TV')
        with open(os.path.join(BASE, filename), 'r', encoding='utf-8') as f:
            content = f.read()
            # Replace all variations of the placeholder
            content = content.replace('{{SITE_NAME}}', site_name)
            content = content.replace('ZUZZ TV', site_name)
            return HttpResponse(content)
    except Exception as e:
        log(f"[PAGE] Error serving {filename}: {e}")
        return HttpResponse("Page not found", status=404)

def faq_page(r):
    return serve_html_page('faq.html')

def why_zuzz_page(r):
    return serve_html_page('why_zuzz.html')

def terms_page(r):
    return serve_html_page('terms.html')

def privacy_page(r):
    return serve_html_page('privacy.html')

def affiliates_page(r):
    return serve_html_page('affiliates.html')

def contact_page(r):
    return serve_html_page('contact.html')

def forgot_password_page(r):
    return serve_html_page('forgot_password.html')

def player_page(r):
    ch_id=r.GET.get('ch','')
    return HttpResponse(f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Watch - ZUZZ TV</title>
<link rel="manifest" href="/manifest.json"><meta name="theme-color" content="#ff5722">
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
:root{{--p:#ff5722;--bg:#000;--card:rgba(0,0,0,.8);--txt:#fff;--mut:#aaa}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100%;height:100%;overflow:hidden}}
body{{font-family:system-ui;background:#000;color:var(--txt)}}
.player-container{{position:relative;width:100vw;height:100vh;background:#000}}
.player-container video,.player-container iframe{{position:absolute;top:0;left:0;width:100%;height:100%;border:none;object-fit:contain}}
.top-bar{{position:absolute;top:0;left:0;right:0;padding:15px 20px;background:linear-gradient(to bottom,rgba(0,0,0,.8),transparent);display:flex;align-items:center;justify-content:space-between;z-index:100;opacity:0;transition:opacity .3s}}
.player-container:hover .top-bar{{opacity:1}}
.back-btn{{color:var(--p);text-decoration:none;font-size:14px;display:flex;align-items:center;gap:5px}}
.back-btn:hover{{text-decoration:underline}}
.ch-title{{display:flex;align-items:center;gap:10px}}
.live-badge{{background:#f00;color:#fff;padding:4px 10px;border-radius:4px;font-size:11px;font-weight:700;animation:pulse 1.5s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.6}}}}
.ch-name{{font-size:16px;font-weight:600}}
.controls{{display:flex;align-items:center;gap:10px}}
.srv-btn{{padding:8px 16px;background:transparent;border:1px solid var(--p);border-radius:6px;color:var(--txt);cursor:pointer;font-size:12px;transition:all .2s}}
.srv-btn:hover,.srv-btn.active{{background:var(--p);border-color:var(--p)}}
.fs-btn{{padding:8px 16px;background:var(--card);border:1px solid #444;border-radius:6px;color:var(--txt);cursor:pointer;font-size:12px}}
.fs-btn:hover{{background:#333}}
.loading{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:var(--mut);font-size:18px}}
.error{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#f55;font-size:18px;text-align:center}}
</style></head>
<body>
<div class="player-container" id="player-container">
<div class="loading" id="loading">⏳ Loading...</div>
<div class="top-bar">
<a href="/" class="back-btn">← Back to matches</a>
<div class="ch-title">
<span class="live-badge">🔴 LIVE</span>
<span class="ch-name" id="ch-name">Loading...</span>
</div>
<div class="controls">
<div id="servers"></div>
<button class="fs-btn" onclick="goFullscreen()">⛶ Fullscreen</button>
</div>
</div>
</div>
<script>
const chId={ch_id or 'null'};
let channel=null;
let hls=null;

async function loadChannel(){{
    if(!chId){{showError('No channel specified');return;}}
    try{{
        const r=await fetch('/api/data');
        const data=await r.json();
        channel=(data.channels||[]).find(c=>c.id==chId);
        if(!channel){{showError('Channel not found');return;}}
        
        document.getElementById('ch-name').textContent=channel.name;
        document.getElementById('loading').style.display='none';
        
        const servers=channel.servers||[channel.iframe];
        if(servers.length>1){{
            document.getElementById('servers').innerHTML=servers.map((s,i)=>
                `<button class="srv-btn ${{i===0?'active':''}}" onclick="switchServer(${{i}})">Server ${{i+1}}</button>`
            ).join('');
        }}
        
        playServer(0);
    }}catch(e){{
        showError('Failed to load channel');
    }}
}}

function playServer(idx){{
    const servers=channel.servers||[channel.iframe];
    const url=servers[idx];
    if(!url){{showError('No stream URL');return;}}
    
    document.querySelectorAll('.srv-btn').forEach((b,i)=>b.classList.toggle('active',i===idx));
    
    const container=document.getElementById('player-container');
    const oldVideo=container.querySelector('video');
    const oldIframe=container.querySelector('iframe');
    if(oldVideo)oldVideo.remove();
    if(oldIframe)oldIframe.remove();
    
    if(url.includes('iframe')||url.includes('embed')||url.includes('.html')||(!url.includes('.m3u8')&&!url.includes('.mp4')&&!url.includes('.ts'))){{
        const iframe=document.createElement('iframe');
        iframe.src=url;
        iframe.allowFullscreen=true;
        iframe.allow='autoplay; fullscreen';
        container.appendChild(iframe);
    }}else{{
        const video=document.createElement('video');
        video.id='video';
        video.controls=true;
        video.autoplay=true;
        video.playsInline=true;
        container.appendChild(video);
        
        if(url.includes('.m3u8')){{
            if(Hls.isSupported()){{
                if(hls)hls.destroy();
                hls=new Hls();
                hls.loadSource(url);
                hls.attachMedia(video);
            }}else if(video.canPlayType('application/vnd.apple.mpegurl')){{
                video.src=url;
            }}
        }}else{{
            video.src=url;
        }}
        video.play().catch(e=>console.log('Autoplay blocked'));
    }}
}}

function switchServer(idx){{playServer(idx);}}

function showError(msg){{
    document.getElementById('loading').innerHTML='<span style="color:#f55">'+msg+'</span>';
}}

function goFullscreen(){{
    const el=document.getElementById('player-container');
    if(el.requestFullscreen)el.requestFullscreen();
    else if(el.webkitRequestFullscreen)el.webkitRequestFullscreen();
    else if(el.msRequestFullscreen)el.msRequestFullscreen();
}}

loadChannel();
</script>
</body></html>''')

urlpatterns=[
    path('',home),path('admin',admin_login),path('admin/',admin_login),path('admin/dashboard',admin_dash),path('admin/dashboard/',admin_dash),
    path('admin/m3u',m3u_page),path('admin/m3u/',m3u_page),path('admin/m3u/<int:list_id>',m3u_player),path('admin/m3u/<int:list_id>/',m3u_player),
    path('admin/import',import_events_page),path('admin/import/',import_events_page),
    path('player',player_page),path('player/',player_page),
    path('login',viewer_login_page),path('login/',viewer_login_page),path('register',viewer_register_page),path('register/',viewer_register_page),
    path('welcome',welcome_page),path('welcome/',welcome_page),
    path('payment',payment_page),path('payment/',payment_page),
    path('forgot-password',forgot_password_page),path('forgot-password/',forgot_password_page),
    path('faq',faq_page),path('faq/',faq_page),
    path('why-zuzz',why_zuzz_page),path('why-zuzz/',why_zuzz_page),
    path('terms',terms_page),path('terms/',terms_page),
    path('privacy',privacy_page),path('privacy/',privacy_page),
    path('affiliates',affiliates_page),path('affiliates/',affiliates_page),
    path('contact',contact_page),path('contact/',contact_page),
    path('manifest.json',manifest),path('sw.js',sw),path('icon-192.png',icon_192),path('icon-512.png',icon_512),
    path('api/login',api_login),path('api/viewer/register',api_viewer_register),path('api/viewer/login',api_viewer_login),
    path('api/viewer/logout',api_viewer_logout),path('api/viewer/delete',api_viewer_delete),path('api/viewer/manage',api_viewer_manage),path('api/viewer/profile',api_viewer_profile),path('api/favorites',api_favorites),
    path('api/plans',api_plans),path('api/subscribe',api_subscribe),path('api/data',api_data),path('api/track',api_track),
    path('api/channel',api_channel),path('api/channel/delete',api_channel_del),path('api/category',api_category),path('api/category/delete',api_category_del),
    path('api/user',api_user),path('api/user/delete',api_user_del),path('api/m3u/lists',api_m3u_lists),path('api/m3u/import',api_m3u_import),
    path('api/m3u/channels/<int:list_id>',api_m3u_channels),path('api/m3u/delete',api_m3u_del),path('api/m3u/refresh',api_m3u_refresh),
    path('api/analytics',api_analytics),path('api/settings',api_settings),path('api/viewers',api_viewers),
    path('api/plans',api_plans),path('api/plan',api_plan),path('api/plan/delete',api_plan_delete),
    path('api/matches',api_matches),path('api/match/save',api_match_save),path('api/match/delete',api_match_delete),path('api/match/toggle',api_match_toggle),
    path('api/import/fetch-events',api_import_fetch_events),path('api/import/save-events',api_import_save_events),
    path('api/upload-icon',api_upload_icon),
    path('api/forgot-password',api_forgot_password),path('api/verify-reset-code',api_verify_reset_code),path('api/reset-password',api_reset_password),path('api/test-smtp',api_test_smtp),
    path('uploads/<str:filename>',serve_upload),
]

if __name__=='__main__':
    from django.core.management import execute_from_command_line
    scheduler.start()
    print("\n"+"="*50+"\n   🔥 ZUZZ TV v2.0 Ready!\n"+"="*50)
    print("\n   📺 Site:     http://127.0.0.1:8000")
    print("   🔐 Admin:    http://127.0.0.1:8000/admin")
    print("   👤 Login:    http://127.0.0.1:8000/login")
    print("   📝 Register: http://127.0.0.1:8000/register")
    print("\n   👨‍💼 Admin: admin / admin123")
    print("\n   ✨ New Features: PWA, Auto-Refresh, Subscriptions, Analytics, Security")
    print("="*50+"\n")
    execute_from_command_line(['','runserver','0.0.0.0:8000','--noreload'])
