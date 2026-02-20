import psutil
import requests
import base64
import time
import urllib3
import sys
from datetime import datetime
import csv
import os
import threading
import winreg
import builtins

# ==========================================
# 配置区
# ==========================================
# [开关] 开机自启 (1 = 开启, 0 = 关闭)
AUTO_STARTUP = 1
# [推送] 你的 Server酱 Key (填入后自动开启微信推送)
SERVERCHAN_KEY = ""
# [名单] 专属监控白名单 (注意：必须带上 # 号和后面的数字标签)
# 留空 [] 则默认监控所有人。示例: ["兵部尚书蒋劲夫#76519", "煎蛋小蘑菇#78594"]
TARGET_FRIENDS = []


sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOCAL_PROXY = {"http": None, "https": None}
csv_lock = threading.Lock()

class LoLMonitor:
    def __init__(self):
        self.port, self.password, self.headers = None, None, None
        self.friends_cache = {}
        self.is_first_scan = True

        # 内置英雄字典 (全网最全)
        self.champ_dict = {
            "1": "安妮", "2": "奥拉夫", "3": "加里奥", "4": "卡牌", "5": "赵信", "6": "厄加特",
            "7": "妖姬", "8": "吸血鬼", "9": "稻草人", "10": "凯尔", "11": "剑圣", "12": "牛头",
            "13": "瑞兹", "14": "塞恩", "15": "轮子妈", "16": "星妈", "17": "提莫", "18": "小炮",
            "19": "狼人", "20": "努努", "21": "女枪", "22": "寒冰", "23": "蛮王", "24": "武器",
            "25": "莫甘娜", "26": "时光", "27": "炼金", "28": "寡妇", "29": "老鼠", "30": "死歌",
            "31": "大虫子", "32": "阿木木", "33": "龙龟", "34": "冰鸟", "35": "小丑", "36": "蒙多",
            "37": "琴女", "38": "卡萨丁", "39": "刀妹", "40": "风女", "41": "船长", "42": "飞机",
            "43": "卡尔玛", "44": "宝石", "45": "小法", "48": "巨魔", "50": "乌鸦", "51": "女警",
            "53": "机器人", "54": "石头人", "55": "卡特", "56": "梦魇", "57": "大树", "58": "鳄鱼",
            "59": "皇子", "60": "蜘蛛", "61": "发条", "62": "猴子", "63": "火男", "64": "盲僧",
            "67": "薇恩", "68": "兰博", "69": "蛇女", "72": "蝎子", "74": "大头", "75": "狗头",
            "76": "豹女", "77": "乌迪尔", "78": "波比", "79": "酒桶", "80": "潘森", "81": "EZ",
            "82": "铁男", "83": "掘墓", "84": "阿卡丽", "85": "凯南", "86": "盖伦", "89": "日女",
            "90": "蚂蚱", "91": "男刀", "92": "锐雯", "96": "大嘴", "98": "慎", "99": "拉克丝",
            "101": "泽拉斯", "102": "龙女", "103": "阿狸", "104": "男枪", "105": "小鱼人", "106": "狗熊",
            "107": "狮子狗", "110": "韦鲁斯", "111": "泰坦", "112": "三只手", "113": "猪妹", "114": "剑姬",
            "115": "炸弹人", "117": "璐璐", "119": "德莱文", "120": "人马", "121": "螳螂", "122": "诺手",
            "126": "杰斯", "127": "冰女", "131": "皎月", "133": "奎因", "134": "辛德拉", "136": "龙王",
            "141": "凯隐", "142": "佐伊", "143": "婕拉", "145": "卡莎", "147": "萨勒芬妮", "150": "纳尔",
            "154": "扎克", "157": "亚索", "161": "大眼", "163": "岩雀", "164": "青钢影", "166": "阿克尚",
            "200": "卑尔维斯", "201": "布隆", "202": "烬", "203": "千珏", "221": "泽丽", "222": "金克丝",
            "223": "塔姆", "233": "贝蕾亚", "234": "佛耶戈", "235": "赛娜", "236": "卢锡安", "238": "劫",
            "240": "克烈", "245": "艾克", "246": "奇亚娜", "254": "蔚", "266": "剑魔", "267": "娜美",
            "268": "沙皇", "350": "悠米", "360": "莎弥拉", "412": "锤石", "420": "俄洛伊", "421": "挖掘机",
            "427": "艾翁", "429": "滑板鞋", "432": "巴德", "497": "洛", "498": "霞", "516": "奥恩",
            "517": "塞拉斯", "518": "妮蔻", "523": "厄斐琉斯", "526": "芮尔", "555": "派克", "777": "永恩",
            "875": "瑟提", "876": "莉莉娅", "887": "格温", "888": "烈娜塔", "893": "兔子", "901": "小火龙",
            "910": "异画师"
        }

    # ==========================================
    # 🌟 微信推送模块 (仅推战绩)
    # ==========================================
    def send_push(self, title, content=""):
        if not SERVERCHAN_KEY: return
        try:
            url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
            requests.post(url, data={"title": title, "desp": content}, timeout=5)
        except Exception:
            pass

    def get_mode_name(self, queue_id):
        if not queue_id: return "未知模式"
        qid = str(queue_id).upper()
        if "RANKED_SOLO" in qid: return "单双排位"
        if "RANKED_FLEX" in qid: return "灵活组排"
        if "ARAM" in qid: return "极地大乱斗"
        if "KIWI" in qid: return "海克斯大乱斗"
        if "TFT" in qid: return "云顶之弈"
        if "CHERRY" in qid: return "斗魂竞技场"
        if "URF" in qid: return "无限火力"
        if "NORMAL" in qid: return "匹配模式"
        if "PRACTICETOOL" in qid: return "训练模式"
        return f"未知({queue_id})"

    def log_to_csv(self, name, action, detail):
        file_exists = os.path.isfile('lol_log.csv')
        with csv_lock:
            try:
                with open('lol_log.csv', mode='a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['时间', '好友ID', '动作', '详情'])
                    writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, action, detail])
            except: pass

    def connect_client(self):
        print("正在寻找英雄联盟客户端...")
        while True:
            for process in psutil.process_iter(['name', 'cmdline']):
                try:
                    if process.info['name'] == 'LeagueClientUx.exe':
                        cmdline = process.info['cmdline']
                        self.port = [a.split('=')[1] for a in cmdline if '--app-port=' in a][0]
                        self.password = [a.split('=')[1] for a in cmdline if '--remoting-auth-token=' in a][0]
                        auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
                        self.headers = {'Authorization': f'Basic {auth}', 'Accept': 'application/json'}
                        print(f"[+] 连接成功！端口: {self.port}")
                        return
                except: pass
            time.sleep(2)

    def get_friends(self):
        url = f"https://127.0.0.1:{self.port}/lol-chat/v1/friends"
        try:
            return requests.get(url, headers=self.headers, verify=False, proxies=LOCAL_PROXY, timeout=5).json()
        except:
            self.connect_client()
            return []

    def async_fetch_stats(self, display_name, puuid, mode_name, champ_name):
        if "云顶" in mode_name or "训练" in mode_name:
            msg = f"该模式无KDA数据 (模式: {mode_name})"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 [战报] {display_name}: {msg}")
            self.send_push(f"LOL动态: {display_name} 结束游玩", msg)
            return

        for attempt in range(12):
            time.sleep(8)
            url = f"https://127.0.0.1:{self.port}/lol-match-history/v1/products/lol/{puuid}/matches?begIndex=0&endIndex=1"
            try:
                res = requests.get(url, headers=self.headers, verify=False, proxies=LOCAL_PROXY, timeout=5)
                if res.status_code == 200:
                    games = res.json().get('games', {}).get('games', [])
                    if not games: continue
                    last_game = games[0]

                    gc = last_game.get('gameCreation', 0)
                    if gc < 20000000000: gc *= 1000
                    if (time.time() * 1000 - gc) > 4 * 3600 * 1000: continue

                    p_id = None
                    for pi in last_game.get('participantIdentities', []):
                        if pi.get('player', {}).get('puuid') == puuid:
                            p_id = pi.get('participantId')
                            break

                    stats = None
                    if p_id:
                        for p in last_game.get('participants', []):
                            if p.get('participantId') == p_id:
                                stats = p.get('stats', {})
                                break
                    else:
                        if len(last_game.get('participants', [])) > 0:
                            stats = last_game.get('participants', [])[0].get('stats', {})

                    if stats:
                        total_sec = last_game.get('gameDuration', 0)
                        if total_sec > 5000: total_sec //= 1000
                        m, s = divmod(total_sec, 60)

                        kills, deaths, assists = stats.get('kills', 0), stats.get('deaths', 0), stats.get('assists', 0)
                        win_tag = "[胜利]" if stats.get('win', False) else "[失败]"
                        res_str = f"{win_tag} 模式:[{mode_name}] 英雄:[{champ_name}] KDA:[{kills}]/[{deaths}]/[{assists}] (时长:{m}分{s}秒)"

                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 [战报] {display_name} -> {res_str}")
                        self.log_to_csv(display_name, "战绩", res_str)

                        self.send_push(f"🏆 LOL战报: {display_name} {win_tag}", res_str)
                        return
            except: pass

        print(f"[{datetime.now().strftime('%H:%M:%S')}]  [战报] {display_name} 战绩刷新超时(服务器延迟)。")

    def process_status(self, friend):
        name = friend.get('gameName') or friend.get('name') or "未知"
        tag = friend.get('gameTag', '')
        display_name = f"{name}#{tag}" if tag else name

        # ==========================================
        #如果设置了白名单，且该好友不在名单内，直接跳过！
        # ==========================================
        if TARGET_FRIENDS and (display_name not in TARGET_FRIENDS):
            return

        puuid = friend.get('puuid')
        current_status = friend.get('availability')
        lol_data = friend.get('lol', {})
        is_in_game = (lol_data.get('gameStatus') == 'inGame')
        queue_id = lol_data.get('gameQueueType', '')
        mode_name = self.get_mode_name(queue_id)

        cid = str(lol_data.get('championId', ''))
        cname = self.champ_dict.get(cid, f"ID:{cid}") if cid and cid != "0" else ""
        cdisplay = f" -- 使用:[{cname}]" if cname and "云顶" not in mode_name else ""

        played_str = ""
        if is_in_game:
            ts = lol_data.get('timeStamp') or lol_data.get('timestamp') or ''
            if ts:
                try:
                    ts_val = float(ts)
                    if ts_val > 20000000000: ts_val /= 1000.0
                    elapsed = int(time.time() - ts_val)
                    if elapsed > 0:
                        m, s = divmod(elapsed, 60)
                        played_str = f" [已打 {m}分{s}秒]"
                except: pass

        now_time = datetime.now().strftime("%H:%M:%S")

        if display_name not in self.friends_cache:
            self.friends_cache[display_name] = {'is_in_game': is_in_game, 'status': current_status, 'cname': cname,'mode_name':mode_name}
            if self.is_first_scan and (is_in_game or current_status != 'offline'):
                print(f"[{now_time}] [扫描] {display_name} {'正在游戏中 -> '+mode_name+cdisplay+played_str if is_in_game else '当前在线'}")
            return

        old = self.friends_cache[display_name]

        if old['status'] in ['offline', 'mobile'] and current_status in ['chat', 'dnd', 'away']:
            print(f"[{now_time}] [+] {display_name} 上线了")
        elif old['status'] != 'offline' and current_status == 'offline':
            print(f"[{now_time}] [-] {display_name} 下线了")

        if not old['is_in_game'] and is_in_game:
            msg = f"{mode_name}{cdisplay}"
            print(f"[{now_time}] [开始] {display_name} -> {msg}")
            self.log_to_csv(display_name, "开始", mode_name)

        elif old['is_in_game'] and not is_in_game:
            print(f"[{now_time}] [结束] {display_name} 退出游戏，正在拉取官方结算...")
            threading.Thread(target=self.async_fetch_stats, args=(display_name, puuid, old.get('mode_name', mode_name), old.get('cname', '未知'))).start()

        self.friends_cache[display_name].update({'is_in_game': is_in_game, 'status': current_status, 'cname': cname, 'mode_name': mode_name})

    def start(self):
        self.connect_client()
        push_status = "已开启(仅推战绩)" if SERVERCHAN_KEY else "未配置"
        target_status = "全部好友" if not TARGET_FRIENDS else f"已设置 {len(TARGET_FRIENDS)} 位白名单"
        print("-" * 65)
        print(f"[*] 监控已启动 (微信推送: {push_status} | 监控范围: {target_status})")
        print("-" * 65)
        while True:
            friends = self.get_friends()
            if isinstance(friends, list):
                for f in friends: self.process_status(f)
            self.is_first_scan = False
            time.sleep(3)

def handle_startup(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        cmd = f'"{sys.executable}" "{os.path.realpath(__file__)}"'
        if enable == 1:
            winreg.SetValueEx(key, "LOLMonitor", 0, winreg.REG_SZ, cmd)
        else:
            try: winreg.DeleteValue(key, "LOLMonitor")
            except: pass
        winreg.CloseKey(key)
    except: pass

if __name__ == "__main__":
    handle_startup(AUTO_STARTUP)
    LoLMonitor().start()
