from __future__ import annotations

import json
import math
import re
import struct
import sys
import subprocess
import time
import wave
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter import messagebox, simpledialog

APP_DIR = Path(__file__).resolve().parent
LEXICON_PATH = APP_DIR / "lexicon.json"
S2T_OPENCC_PATH = APP_DIR / "s2t_opencc.json"
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "中文转粤语声调"
USER_LEXICON_PATH = SUPPORT_DIR / "我的补充词库.txt"
HISTORY_PATH = SUPPORT_DIR / "输入记录.json"
TONE_AUDIO_DIR = SUPPORT_DIR / "声调音频"

TONE = {
    "1": {"name": "高平", "shape": "高━", "value": "˥", "levels": (5, 5)},
    "2": {"name": "中升高", "shape": "中↗高", "value": "˧˥", "levels": (3, 5)},
    "3": {"name": "中平", "shape": "中━", "value": "˧", "levels": (3, 3)},
    "4": {"name": "低降", "shape": "低↘", "value": "˨˩", "levels": (2, 1)},
    "5": {"name": "低升中", "shape": "低↗中", "value": "˩˧", "levels": (1, 3)},
    "6": {"name": "低平", "shape": "低━", "value": "˨", "levels": (2, 2)},
}
# 中文译音用拼音一样的“形状符号”，避免显示数字：
# ˉ 高平；ˊ 上升；第3声中平不额外加横线；ˋ 下降；ˇ 低升；ˍ 低平。
TONE_BADGE = {"1": "ˉ", "2": "ˊ", "3": "", "4": "ˋ", "5": "ˇ", "6": "ˍ"}


INITIALS = ["gw", "kw", "ng", "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "w", "z", "c", "s", "j"]
INITIAL_TIPS = {
    "b": "近似普通话 b，但不送气", "p": "近似普通话 p，送气", "m": "近似普通话 m", "f": "近似普通话 f",
    "d": "近似普通话 d，但舌尖更靠前", "t": "近似普通话 t，送气", "n": "近似普通话 n", "l": "近似普通话 l",
    "g": "近似普通话 g，但不送气", "k": "近似普通话 k，送气", "ng": "鼻音，像普通话“昂”的开头鼻音", "h": "近似普通话 h",
    "gw": "g 后面接圆唇 w", "kw": "k 后面接圆唇 w", "w": "近似普通话 w", "z": "近似普通话 z/j 之间，舌尖音", "c": "近似普通话 c/q 之间，送气舌尖音", "s": "近似普通话 s/x 之间", "j": "近似普通话 y",
    "": "零声母，直接从韵母开始读",
}
TONE_TEACH = {
    "1": "高处平着走：从高音开始，保持平稳。",
    "2": "中间往上升：从中音升到高音，像普通话二声的感觉。",
    "3": "中间平着走：在中音位置保持平稳。",
    "4": "低处往下落：从低音再往更低处落，是唯一明显下降的常用调。",
    "5": "低处往上升：从低音升到中音，幅度比第2声低。",
    "6": "低处平着走：在低音位置保持平稳。",
}


def split_initial_final(base: str) -> tuple[str, str]:
    for initial in INITIALS:
        if base.startswith(initial) and len(base) > len(initial):
            return initial, base[len(initial):]
    return "", base


def tone_part_label(num: str) -> str:
    if num == "3":
        return "中平"
    return TONE_BADGE.get(num, "") or "中平"


def split_sound_text(base: str, num: str, *, compact: bool = False) -> str:
    initial, final = split_initial_final(base)
    initial_text = initial or "零声母"
    final_text = final or "—"
    sep = "+" if compact else " + "
    return sep.join([initial_text, final_text, tone_part_label(num)])


def split_sound_line_for_jp(jp: str, *, compact: bool = False, joiner: str = " / ") -> str:
    parts = []
    for base, num in split_jp(jp):
        if base == "?":
            parts.append("?")
        else:
            parts.append(split_sound_text(base, num, compact=compact))
    return joiner.join(parts)


def card_split_sound_line(jp: str) -> str:
    # 词卡空间有限：用“声母+韵母+形状”紧凑显示，中平写“平”，不写数字。
    parts = []
    for base, num in split_jp(jp):
        if base == "?":
            parts.append("?")
            continue
        initial, final = split_initial_final(base)
        initial_text = initial or "零"
        tone = "平" if num == "3" else TONE_BADGE.get(num, "")
        parts.append(f"{initial_text}+{final}{tone}")
    return " · ".join(parts)


def marked_syllable(base: str, num: str) -> str:
    mark = TONE_BADGE.get(num, "")
    return f"{base}{mark}" if mark else f"{base}（中平）"


def explain_syllable(base: str, num: str) -> str:
    initial, final = split_initial_final(base)
    if num not in TONE:
        return f"{base}：这里先按自定义拆音学习。"
    tone = TONE[num]
    initial_text = initial or "零声母"
    final_text = final or "—"
    initial_tip = INITIAL_TIPS.get(initial, "按粤拼读这个声母")
    return (
        f"{marked_syllable(base, num)}：拆音 {split_sound_text(base, num)}。"
        f"声调 {tone_part_label(num)} {tone['name']} {tone['value']}。{TONE_TEACH[num]}"
        f" 声母提示：{initial_text}，{initial_tip}。韵母：{final_text}。"
    )


def general_tone_guide() -> str:
    return (
        "粤拼怎么看：\n"
        "• 前面的字母是音节，例如 ngo、soeng、heoi。\n"
        "• 后面的 ˉ ˊ ˋ ˇ ˍ 是声调形状，不是音量，是音高走势。\n"
        "• 没有符号的是中平，平着读。\n\n"
        "六种走势：\n"
        "ˉ 高平：高处平着走\n"
        "ˊ 中升高：中间往上升\n"
        "  中平：中间平着走\n"
        "ˋ 低降：低处往下落\n"
        "ˇ 低升中：低处往上升\n"
        "ˍ 低平：低处平着走\n\n"
        "先记三类：平、升、降。上面的折线看高低，下面的符号帮你快速读。"
    )

S2T = str.maketrans({
    "饭": "飯", "谢": "謝", "饮": "飲", "吗": "嗎", "这": "這", "那": "嗰", "个": "個", "们": "哋",
    "说": "講", "听": "聽", "见": "見", "买": "買", "卖": "賣", "车": "車", "钱": "錢", "点": "點",
    "里": "裏", "后": "後", "开": "開", "关": "關", "门": "門", "东": "東", "会": "會", "来": "嚟",
    "过": "過", "还": "還", "没": "冇", "无": "無", "爱": "愛", "电": "電", "话": "話", "书": "書",
    "学": "學", "气": "氣", "龙": "龍", "广": "廣", "国": "國", "语": "語", "汉": "漢", "边": "邊",
    "时": "時", "间": "間", "请": "請", "问": "問", "号": "號", "发": "發", "乐": "樂", "长": "長",
    "着": "著", "带": "帶", "给": "畀", "为": "為", "对": "對", "欢": "歡", "粤": "粵", "儿": "仔",
})

# 普通中文到日常粤语的本地规则。长词优先。
RULES = {
    "不好意思": "唔好意思", "对不起": "對唔住", "對不起": "對唔住", "没关系": "唔緊要", "沒關係": "唔緊要",
    "谢谢你": "多謝你", "謝謝你": "多謝你", "谢谢": "多謝", "謝謝": "多謝", "麻烦你": "唔該你", "麻煩你": "唔該你",
    "请问": "請問", "請問": "請問", "请": "唔該", "請": "唔該",
    "多少钱": "幾多錢", "多少錢": "幾多錢", "为什么": "點解", "為什麼": "點解", "干什么": "做咩", "幹什麼": "做咩",
    "在哪里": "喺邊度", "在哪裏": "喺邊度", "在哪儿": "喺邊度", "在哪兒": "喺邊度", "哪里": "邊度", "哪裏": "邊度", "哪儿": "邊度", "哪兒": "邊度",
    "什么时候": "幾時", "什麼時候": "幾時", "什么时间": "幾時", "什麼時間": "幾時", "什么": "咩", "什麼": "咩", "怎么": "點", "怎麼": "點", "怎么样": "點樣", "怎麼樣": "點樣", "多少": "幾多", "几个": "幾個", "幾個": "幾個",
    "这个": "呢個", "這個": "呢個", "那个": "嗰個", "那個": "嗰個", "这里": "呢度", "這裏": "呢度", "这儿": "呢度", "這兒": "呢度", "那里": "嗰度", "那裏": "嗰度", "那儿": "嗰度", "那兒": "嗰度", "这些": "呢啲", "這些": "呢啲", "那些": "嗰啲", "那些": "嗰啲",
    "现在": "而家", "現在": "而家", "今天": "今日", "明天": "聽日", "昨天": "噚日", "刚才": "頭先", "剛才": "頭先", "一会儿": "一陣", "一會兒": "一陣",
    "今晚几点睡觉": "今晚幾點瞓覺", "今晚幾點睡覺": "今晚幾點瞓覺", "晚上几点睡觉": "夜晚幾點瞓覺", "晚上幾點睡覺": "夜晚幾點瞓覺",
    "几点睡觉": "幾點瞓覺", "幾點睡覺": "幾點瞓覺", "什么时候睡觉": "幾時瞓覺", "什麼時候睡覺": "幾時瞓覺",
    "今晚": "今晚", "明晚": "聽晚", "昨晚": "琴晚", "晚上": "夜晚", "夜里": "夜晚", "夜裏": "夜晚",
    "我们": "我哋", "我們": "我哋", "你们": "你哋", "你們": "你哋", "他们": "佢哋", "他們": "佢哋", "她们": "佢哋", "她們": "佢哋", "它们": "佢哋", "它們": "佢哋", "他": "佢", "她": "佢", "它": "佢",
    "是不是": "係唔係", "是不是": "係唔係", "不是": "唔係", "不是": "唔係", "没有": "冇", "沒有": "冇", "有没有": "有冇", "有沒有": "有冇", "不要": "唔好", "不会": "唔會", "不會": "唔會", "不可以": "唔可以",
    "正在": "喺度", "在": "喺", "是": "係", "的": "嘅", "了": "咗", "吧": "啦", "吗": "嗎", "嗎": "嗎", "不": "唔",
    "喜欢": "鍾意", "喜歡": "鍾意", "觉得": "覺得", "覺得": "覺得", "知道": "知", "认识": "識", "認識": "識",
    "我们去看电影吧": "我哋去睇戲啦", "我們去看電影吧": "我哋去睇戲啦", "我们去看電影吧": "我哋去睇戲啦", "我們去看电影吧": "我哋去睇戲啦",
    "去看电影": "去睇戲", "去看電影": "去睇戲", "看电影": "睇戲", "看電影": "睇戲", "电影票": "戲飛", "電影票": "戲飛", "电影": "電影", "電影": "電影",
    "看见": "睇見", "看見": "睇見", "看到": "睇到", "看": "睇", "听": "聽", "聽": "聽", "说": "講", "說": "講", "告诉": "話畀", "告訴": "話畀", "给": "畀", "給": "畀", "和": "同", "跟": "同",
    "吃饭": "食飯", "吃飯": "食飯", "吃": "食", "喝茶": "飲茶", "喝": "飲",
    "我睡不着": "我瞓唔著", "我睡不著": "我瞓唔著", "睡不着": "瞓唔著", "睡不著": "瞓唔著",
    "我要睡觉": "我要瞓覺", "我要睡覺": "我要瞓覺", "我想睡觉": "我想瞓覺", "我想睡覺": "我想瞓覺", "想睡觉": "想瞓覺", "想睡覺": "想瞓覺", "去睡觉": "去瞓覺", "去睡覺": "去瞓覺",
    "睡觉": "瞓覺", "睡覺": "瞓覺", "睡着": "瞓著", "睡著": "瞓著", "睡醒": "瞓醒", "睡不着": "瞓唔著", "睡不著": "瞓唔著", "睡": "瞓",
    "回家": "返屋企", "回去": "返去", "回来": "返嚟", "回來": "返嚟", "上班": "返工", "下班": "放工", "工作": "做嘢", "学习": "學嘢", "學習": "學嘢", "玩儿": "玩", "玩兒": "玩",
    "鸡腿": "雞腿", "雞腿": "雞腿", "鸡翅": "雞翼", "雞翅": "雞翼", "鸡肉": "雞肉", "雞肉": "雞肉", "烧鸡": "燒雞", "燒雞": "燒雞",
    "一点": "少少", "一點": "少少", "一些": "一啲", "很": "好", "非常": "好", "太": "太", "也": "都", "都": "都", "再": "再", "先": "先",
    "粤语": "粵語", "粵語": "粵語", "广东话": "廣東話", "廣東話": "廣東話", "广州": "廣州", "廣州": "廣州",

    "请帮我": "唔該幫我", "請幫我": "唔該幫我", "帮我": "幫我", "幫我": "幫我", "帮忙": "幫手", "幫忙": "幫手",
    "可以吗": "得唔得", "可以嗎": "得唔得", "好不好": "好唔好", "要不要": "要唔要", "有没有": "有冇", "有沒有": "有冇",
    "我不知道": "我唔知", "不知道": "唔知", "知道了": "知道咗", "知道": "知", "明白了": "明咗", "明白": "明",
    "叫什么名字": "叫咩名", "叫什麼名字": "叫咩名", "名字": "名", "电话": "電話", "電話": "電話", "微信": "微信",
    "我要": "我要", "我想要": "我想要", "你要": "你要", "需要": "需要", "不用": "唔使", "不用了": "唔使喇",
    "哪里有": "邊度有", "哪裏有": "邊度有", "怎么去": "點去", "怎麼去": "點去", "去哪里": "去邊度", "去哪裏": "去邊度",
    "地铁": "地鐵", "地鐵": "地鐵", "公交车": "巴士", "公交車": "巴士", "出租车": "的士", "出租車": "的士", "打车": "搭的士", "打車": "搭的士",
    "酒店": "酒店", "机场": "機場", "機場": "機場", "车站": "車站", "車站": "車站", "厕所": "廁所", "廁所": "廁所",
    "菜单": "餐牌", "菜單": "餐牌", "买单": "埋單", "買單": "埋單", "打包": "拎走", "外卖": "外賣", "外賣": "外賣",
    "好吃": "好食", "难吃": "難食", "難吃": "難食", "好喝": "好飲", "贵": "貴", "貴": "貴", "便宜": "平",
    "一点点": "少少", "一點點": "少少", "很多": "好多", "太多": "太多", "太贵": "太貴", "太貴": "太貴",
    "开心": "開心", "開心": "開心", "生气": "嬲", "生氣": "嬲", "累": "攰", "忙": "忙", "快": "快", "慢": "慢",
    "漂亮": "靚", "好看": "好睇", "不好看": "唔好睇", "厉害": "犀利", "厲害": "犀利", "真的": "真係", "真是": "真係", "就是": "就係",
    "全部": "全部", "一起": "一齊", "马上": "即刻", "馬上": "即刻", "马上来": "即刻嚟", "马上到": "即刻到",
    "等一下": "等陣", "等一等": "等一等", "慢慢来": "慢慢嚟", "慢慢來": "慢慢嚟",
    "早上好": "早晨", "晚上好": "晚安", "晚安": "晚安", "再见": "再見", "再見": "再見",
}
# 查漏补缺：常见不能逐字翻译的日常口语。长词优先。
SUPPLEMENT_RULES = {
    # 看 / 听 / 娱乐
    "我们去看电影吧": "我哋去睇戲啦", "我們去看電影吧": "我哋去睇戲啦", "我们去看電影吧": "我哋去睇戲啦", "我們去看电影吧": "我哋去睇戲啦",
    "去看电影": "去睇戲", "去看電影": "去睇戲", "看电影": "睇戲", "看電影": "睇戲", "电影票": "戲飛", "電影票": "戲飛",
    "看电视": "睇電視", "看電視": "睇電視", "看电视剧": "煲劇", "看電視劇": "煲劇", "追剧": "煲劇", "追劇": "煲劇",
    "看直播": "睇直播", "看视频": "睇片", "看視頻": "睇片", "刷视频": "刷片", "刷視頻": "刷片", "看新闻": "睇新聞", "看新聞": "睇新聞",
    "听歌": "聽歌", "聽歌": "聽歌", "听音乐": "聽音樂", "聽音樂": "聽音樂", "唱歌": "唱歌", "拍照": "影相", "照相": "影相", "拍视频": "拍片", "拍視頻": "拍片",
    # 出行
    "坐公交车": "搭巴士", "坐公交車": "搭巴士", "坐公交": "搭巴士", "坐巴士": "搭巴士",
    "坐地铁": "搭地鐵", "坐地鐵": "搭地鐵", "坐出租车": "搭的士", "坐出租車": "搭的士", "打出租车": "搭的士", "打出租車": "搭的士",
    "买票": "買飛", "買票": "買飛", "车票": "車飛", "車票": "車飛", "机票": "機票", "機票": "機票",
    "怎么走": "點行", "怎麼走": "點行", "怎么坐车": "點搭車", "怎麼坐車": "點搭車", "下车": "落車", "下車": "落車", "上车": "上車", "上車": "上車",
    # 买东西 / 餐饮
    "逛街": "行街", "购物": "買嘢", "購物": "買嘢", "买东西": "買嘢", "買東西": "買嘢", "买菜": "買餸", "買菜": "買餸",
    "点餐": "落單", "點餐": "落單", "点菜": "點菜", "點菜": "點菜", "下单": "落單", "下單": "落單", "结账": "埋單", "結賬": "埋單", "付款": "畀錢", "付钱": "畀錢", "付錢": "畀錢",
    "扫码": "掃碼", "掃碼": "掃碼", "排队": "排隊", "排隊": "排隊", "等位": "等位", "订位": "訂位", "訂位": "訂位",
    "吃早餐": "食早餐", "吃早饭": "食早餐", "吃午饭": "食晏", "吃午飯": "食晏", "吃晚饭": "食晚飯", "吃晚飯": "食晚飯", "吃宵夜": "食宵夜",
    "喝水": "飲水", "喝咖啡": "飲咖啡", "喝奶茶": "飲奶茶", "喝酒": "飲酒",
    # 生活起居
    "上厕所": "去廁所", "上廁所": "去廁所", "去厕所": "去廁所", "去廁所": "去廁所",
    "洗澡": "沖涼", "洗浴": "沖涼", "洗头": "洗頭", "洗頭": "洗頭", "洗脸": "洗面", "洗臉": "洗面", "刷牙": "刷牙",
    "起床": "起身", "起来": "起身", "起來": "起身", "睡醒": "瞓醒", "睡不着": "瞓唔著", "睡不著": "瞓唔著",
    # 学校 / 工作
    "上学": "返學", "上學": "返學", "放学": "放學", "放學": "放學", "上课": "上堂", "上課": "上堂", "下课": "落堂", "下課": "落堂",
    "做作业": "做功課", "做作業": "做功課", "写作业": "做功課", "寫作業": "做功課", "考试": "考試", "考試": "考試",
    "开会": "開會", "開會": "開會", "加班": "加班", "请假": "請假", "請假": "請假",
    # 手机 / 沟通
    "打电话": "打電話", "打電話": "打電話", "发消息": "發信息", "發消息": "發信息", "发短信": "發短信", "發短信": "發短信", "发微信": "發微信", "發微信": "發微信",
    "回消息": "覆信息", "回信息": "覆信息", "上网": "上網", "上網": "上網", "玩手机": "玩手機", "玩手機": "玩手機", "用手机": "用手機", "用手機": "用手機",
    # 医疗 / 住宿
    "看医生": "睇醫生", "看醫生": "睇醫生", "去医院": "去醫院", "去醫院": "去醫院", "吃药": "食藥", "吃藥": "食藥",
    "入住": "入住", "退房": "退房", "订房": "訂房", "訂房": "訂房",
    # 语言学习
    "说粤语": "講粵語", "說粵語": "講粵語", "讲粤语": "講粵語", "講粵語": "講粵語", "学粤语": "學粵語", "學粵語": "學粵語",
}
RULES.update(SUPPLEMENT_RULES)

# 第二轮查漏补缺：优先补“普通话直译会别扭”的高频场景。
AUDIT_RULES = {
    # 看/读/聊
    "去看医生": "去睇醫生", "去看醫生": "去睇醫生", "看病": "睇醫生", "看書": "睇書", "看书": "睇書",
    "读书": "讀書", "讀書": "讀書", "说话": "講嘢", "說話": "講嘢", "聊天": "傾偈", "聊一下": "傾陣偈",
    # 吃喝购物
    "吃东西": "食嘢", "吃東西": "食嘢", "喝东西": "飲嘢", "喝東西": "飲嘢", "我饿了": "我肚餓", "我餓了": "我肚餓", "饿了": "肚餓", "餓了": "肚餓",
    "做饭": "煮飯", "做飯": "煮飯", "做菜": "煮餸", "买衣服": "買衫", "買衣服": "買衫", "便宜点": "平啲", "便宜點": "平啲",
    "不要辣": "唔要辣", "少冰": "少冰", "多冰": "多冰", "打包带走": "拎走", "打包帶走": "拎走",
    # 出行/地点
    "坐车": "搭車", "坐車": "搭車", "地铁站": "地鐵站", "地鐵站": "地鐵站", "公交站": "巴士站", "公交车站": "巴士站", "巴士站": "巴士站",
    "去商场": "去商場", "去商場": "去商場", "逛商场": "行商場", "逛商場": "行商場", "左转": "轉左", "左轉": "轉左", "右转": "轉右", "右轉": "轉右", "直走": "直行",
    # 手机/网络
    "充电": "叉電", "充電": "叉電", "手机没电": "手機冇電", "手機冇電": "手機冇電", "网络不好": "網絡唔好", "網絡不好": "網絡唔好", "网不好": "網唔好", "網不好": "網唔好",
    "找不到": "搵唔到", "找不着": "搵唔到", "找不著": "搵唔到", "还没有": "仲未", "還沒有": "仲未", "还没": "仲未", "還沒": "仲未",
    # 医疗/住宿/生活
    "不舒服": "唔舒服", "头痛": "頭痛", "頭痛": "頭痛", "头疼": "頭痛", "發燒": "發燒", "发烧": "發燒", "咳嗽": "咳", "口渴": "口渴",
    "办理入住": "入住", "辦理入住": "入住", "办理退房": "退房", "辦理退房": "退房", "洗衣服": "洗衫", "洗衣": "洗衫",
    "一会见": "一陣見", "一會見": "一陣見", "马上回来": "即刻返嚟", "馬上回來": "即刻返嚟",
}
RULES.update(AUDIT_RULES)

# 第三轮批量检查补漏：把常见“问句/状态句”改成更自然的日常粤语。
AUDIT_RULES_2 = {
    # 基础回应/寒暄
    "拜拜": "拜拜", "没事": "冇事", "沒事": "冇事", "没问题": "冇問題", "沒問題": "冇問題",
    "不可以": "唔得", "不行": "唔得", "好的": "好呀", "好吧": "好呀", "行不行": "得唔得", "辛苦了": "辛苦晒", "辛苦啦": "辛苦晒",
    # 吃饭喝水/餐厅
    "你吃饭了吗": "你食咗飯未", "你吃飯了嗎": "你食咗飯未", "吃饭了吗": "食咗飯未", "吃飯了嗎": "食咗飯未",
    "我吃饱了": "我食飽喇", "我吃飽了": "我食飽喇", "吃饱了": "食飽喇", "吃飽了": "食飽喇",
    "我渴了": "我口渴", "我渴": "我口渴", "渴了": "口渴", "渴": "口渴",
    "我要吃饭": "我要食飯", "我要吃飯": "我要食飯", "我想吃东西": "我想食嘢", "我想吃東西": "我想食嘢",
    "可以打包吗": "可唔可以拎走", "可以打包嗎": "可唔可以拎走", "可以打包不": "可唔可以拎走",
    "不要冰": "走冰", "不要放冰": "走冰", "少放辣": "少辣", "不要放辣": "唔要辣", "等位多久": "等位要幾耐", "等位多長時間": "等位要幾耐",
    "有菜单吗": "有冇餐牌", "有菜單嗎": "有冇餐牌", "有位置吗": "有冇位", "有位置嗎": "有冇位", "排队吗": "使唔使排隊", "排隊嗎": "使唔使排隊",
    # 购物/支付
    "可以便宜点吗": "可唔可以平啲", "可以便宜點嗎": "可唔可以平啲", "我想试一下": "我想試吓", "我想試一下": "我想試吓",
    "可以刷卡吗": "可唔可以碌卡", "可以刷卡嗎": "可唔可以碌卡", "可以扫码吗": "可唔可以掃碼", "可以掃碼嗎": "可唔可以掃碼",
    "有发票吗": "有冇發票", "有發票嗎": "有冇發票", "可以开发票吗": "可唔可以開發票", "可以開發票嗎": "可唔可以開發票",
    "我要退货": "我要退貨", "我要退貨": "我要退貨",
    # 出行/方向
    "到了吗": "到咗未", "到了嗎": "到咗未", "我迷路了": "我蕩失路", "我迷路咗": "我蕩失路", "迷路了": "蕩失路", "迷路": "蕩失路", "找不到路": "搵唔到路",
    # 起居/学校/表达
    "我起床了": "我起身咗", "我剛起床": "我頭先起身", "我刚起床": "我頭先起身",
    "我不会写": "我唔識寫", "我不會寫": "我唔識寫", "不会写": "唔識寫", "不會寫": "唔識寫",
    "我听不懂": "我聽唔明", "我聽不懂": "我聽唔明", "听不懂": "聽唔明", "聽不懂": "聽唔明",
    "请再说一次": "唔該再講多次", "請再說一次": "唔該再講多次", "再说一次": "再講多次", "再說一次": "再講多次", "慢一点说": "講慢少少", "慢一點說": "講慢少少",
    # 工作/状态
    "我迟到了": "我遲到咗", "我遲到了": "我遲到咗", "迟到了": "遲到咗", "遲到了": "遲到咗",
    "我今天很忙": "我今日好忙", "我今天好忙": "我今日好忙", "我在家": "我喺屋企", "在家": "喺屋企", "你现在忙吗": "你而家忙唔忙", "你現在忙嗎": "你而家忙唔忙",
    # 医疗/求助
    "我肚子痛": "我肚痛", "我肚子疼": "我肚痛", "肚子痛": "肚痛", "肚子疼": "肚痛", "我牙痛": "我牙痛", "我牙疼": "我牙痛",
    "救命": "救命", "打急救电话": "打急救電話", "打急救電話": "打急救電話", "药店": "藥房", "藥店": "藥房",
    # 酒店/设施
    "我订了房间": "我訂咗房", "我訂了房間": "我訂咗房", "有没有房间": "有冇房", "有沒有房間": "有冇房", "房间多少钱": "房幾多錢", "房間多少錢": "房幾多錢",
    "我要换房": "我要換房", "我要換房": "我要換房", "空调坏了": "冷氣壞咗", "空調壞了": "冷氣壞咗", "空调": "冷氣", "空調": "冷氣", "没有热水": "冇熱水", "沒有熱水": "冇熱水",
    # 手机/网络
    "有没有wifi": "有冇無線網絡", "有沒有wifi": "有冇無線網絡", "有没有WiFi": "有冇無線網絡", "有沒有WiFi": "有冇無線網絡", "wifi": "無線網絡", "WiFi": "無線網絡",
    "密码是什么": "密碼係咩", "密碼是什麼": "密碼係咩", "我上不了网": "我上唔到網", "我上不了網": "我上唔到網", "上不了网": "上唔到網", "上不了網": "上唔到網",
    "已经好了": "搞掂咗", "已經好了": "搞掂咗", "已经好": "搞掂", "已經好": "搞掂",
    # 娱乐/陪同/天气
    "可以拍照吗": "可唔可以影相", "可以拍照嗎": "可唔可以影相", "帮我拍照": "幫我影相", "幫我拍照": "幫我影相", "你等我一下": "你等我陣", "等我一下": "等我陣",
    "今天很冷": "今日好凍", "今天好冷": "今日好凍", "下雨了": "落雨喇", "下雨咗": "落雨喇", "带伞": "帶遮", "帶傘": "帶遮",
    "我会一点粤语": "我識少少粵語", "我會一點粵語": "我識少少粵語", "我不会粤语": "我唔識粵語", "我不會粵語": "我唔識粵語",
}
RULES.update(AUDIT_RULES_2)
RULE_LIST = sorted(RULES.items(), key=lambda item: len(item[0]), reverse=True)

EXTRA_JP = {
    "我哋": "ngo5 dei6", "你哋": "nei5 dei6", "佢哋": "keoi5 dei6", "佢": "keoi5",
    "呢度": "ni1 dou6", "嗰度": "go2 dou6", "呢個": "ni1 go3", "嗰個": "go2 go3", "呢啲": "ni1 di1", "嗰啲": "go2 di1",
    "邊度": "bin1 dou6", "邊個": "bin1 go3", "點解": "dim2 gaai2", "點樣": "dim2 joeng6", "幾時": "gei2 si4", "幾多": "gei2 do1", "幾多錢": "gei2 do1 cin2",
    "而家": "ji4 gaa1", "今日": "gam1 jat6", "今晚": "gam1 maan5", "夜晚": "je6 maan5", "聽晚": "ting1 maan5", "琴晚": "kam4 maan5", "聽日": "ting1 jat6", "噚日": "cam4 jat6", "頭先": "tau4 sin1", "一陣": "jat1 zan6",
    "幾點": "gei2 dim2", "幾時": "gei2 si4", "幾點瞓覺": "gei2 dim2 fan3 gaau3", "今晚幾點瞓覺": "gam1 maan5 gei2 dim2 fan3 gaau3", "夜晚幾點瞓覺": "je6 maan5 gei2 dim2 fan3 gaau3",
    "唔係": "m4 hai6", "係唔係": "hai6 m4 hai6", "冇": "mou5", "有冇": "jau5 mou5", "唔好": "m4 hou2", "唔會": "m4 wui5", "唔可以": "m4 ho2 ji5",
    "喺": "hai2", "喺度": "hai2 dou6", "嘅": "ge3", "咗": "zo2", "咩": "me1", "啦": "laa1", "嗎": "maa3",
    "鍾意": "zung1 ji3", "識": "sik1", "睇": "tai2", "睇見": "tai2 gin3", "睇到": "tai2 dou2", "睇戲": "tai2 hei3", "去睇戲": "heoi3 tai2 hei3", "我哋去睇戲啦": "ngo5 dei6 heoi3 tai2 hei3 laa1", "電影": "din6 jing2", "戲飛": "hei3 fei1", "講": "gong2", "話畀": "waa6 bei2", "畀": "bei2", "同": "tung4",
    "食飯": "sik6 faan6", "飲茶": "jam2 caa4",
    "我瞓覺": "ngo5 fan3 gaau3", "我要瞓覺": "ngo5 jiu3 fan3 gaau3", "我想瞓覺": "ngo5 soeng2 fan3 gaau3", "去瞓覺": "heoi3 fan3 gaau3",
    "我瞓唔著": "ngo5 fan3 m4 zoek6", "瞓覺": "fan3 gaau3", "瞓": "fan3", "瞓著": "fan3 zoek6", "瞓醒": "fan3 seng2", "瞓唔著": "fan3 m4 zoek6",
    "返屋企": "faan1 uk1 kei5", "返去": "faan1 heoi3", "返嚟": "faan1 lai4", "返工": "faan1 gung1", "放工": "fong3 gung1", "做嘢": "zou6 je5", "學嘢": "hok6 je5",
    "少少": "siu2 siu2", "一啲": "jat1 di1", "多謝": "do1 ze6", "唔該": "m4 goi1", "唔該你": "m4 goi1 nei5", "唔緊要": "m4 gan2 jiu3", "對唔住": "deoi3 m4 zyu6", "唔好意思": "m4 hou2 ji3 si1",

    "唔該幫我": "m4 goi1 bong1 ngo5", "幫手": "bong1 sau2", "幫我": "bong1 ngo5", "得唔得": "dak1 m4 dak1", "好唔好": "hou2 m4 hou2", "要唔要": "jiu3 m4 jiu3",
    "我唔知": "ngo5 m4 zi1", "唔知": "m4 zi1", "明咗": "ming4 zo2", "明": "ming4", "叫咩名": "giu3 me1 meng2", "名": "meng2",
    "唔使": "m4 sai2", "唔使喇": "m4 sai2 laa3", "邊度有": "bin1 dou6 jau5", "點去": "dim2 heoi3", "去邊度": "heoi3 bin1 dou6",
    "地鐵": "dei6 tit3", "巴士": "baa1 si6", "的士": "dik1 si2", "搭的士": "daap3 dik1 si2", "酒店": "zau2 dim3", "機場": "gei1 coeng4", "車站": "ce1 zaam6", "廁所": "ci3 so2",
    "餐牌": "caan1 paai2", "埋單": "maai4 daan1", "拎走": "ling1 zau2", "外賣": "ngoi6 maai6", "好食": "hou2 sik6", "難食": "naan4 sik6", "好飲": "hou2 jam2", "貴": "gwai3", "平": "peng4",
    "好多": "hou2 do1", "太貴": "taai3 gwai3", "開心": "hoi1 sam1", "嬲": "nau1", "攰": "gui6", "忙": "mong4", "靚": "leng3", "好睇": "hou2 tai2", "唔好睇": "m4 hou2 tai2", "犀利": "sai1 lei6", "真係": "zan1 hai6", "就係": "zau6 hai6",
    "一齊": "jat1 cai4", "即刻": "zik1 hak1", "即刻嚟": "zik1 hak1 lai4", "即刻到": "zik1 hak1 dou3", "等陣": "dang2 zan6", "慢慢嚟": "maan6 maan6 lai4",
    "雞腿": "gai1 teoi2", "雞翼": "gai1 jik6", "雞肉": "gai1 juk6", "燒雞": "siu1 gai1", "炸雞": "zaa3 gai1", "雞扒": "gai1 paa2",
}

SUPPLEMENT_JP = {
    # 看 / 听 / 娱乐
    "睇戲": "tai2 hei3", "去睇戲": "heoi3 tai2 hei3", "電影": "din6 jing2", "戲飛": "hei3 fei1",
    "睇電視": "tai2 din6 si6", "煲劇": "bou1 kek6", "睇直播": "tai2 zik6 bo3", "睇片": "tai2 pin2", "刷片": "caat3 pin2", "睇新聞": "tai2 san1 man4",
    "聽歌": "teng1 go1", "聽音樂": "teng1 jam1 ngok6", "唱歌": "coeng3 go1", "影相": "jing2 soeng2", "拍片": "paak3 pin2",
    # 出行
    "搭巴士": "daap3 baa1 si6", "搭地鐵": "daap3 dei6 tit3", "搭的士": "daap3 dik1 si2", "買飛": "maai5 fei1", "車飛": "ce1 fei1", "機票": "gei1 piu3",
    "點行": "dim2 haang4", "點搭車": "dim2 daap3 ce1", "落車": "lok6 ce1", "上車": "soeng5 ce1", "搭車": "daap3 ce1",
    # 买东西 / 餐饮
    "行街": "haang4 gaai1", "買嘢": "maai5 je5", "買餸": "maai5 sung3", "落單": "lok6 daan1", "點菜": "dim2 coi3", "畀錢": "bei2 cin2",
    "掃碼": "sou3 maa5", "排隊": "paai4 deoi6", "等位": "dang2 wai2", "訂位": "deng6 wai2",
    "食早餐": "sik6 zou2 caan1", "食晏": "sik6 aan3", "食晚飯": "sik6 maan5 faan6", "食宵夜": "sik6 siu1 je6",
    "飲水": "jam2 seoi2", "飲咖啡": "jam2 gaa3 fe1", "飲奶茶": "jam2 naai5 caa4", "飲酒": "jam2 zau2",
    # 生活起居
    "去廁所": "heoi3 ci3 so2", "沖涼": "cung1 loeng4", "洗頭": "sai2 tau4", "洗面": "sai2 min6", "刷牙": "caat3 ngaa4",
    "起身": "hei2 san1", "瞓醒": "fan3 seng2", "瞓唔著": "fan3 m4 zoek6",
    # 学校 / 工作
    "返學": "faan1 hok6", "放學": "fong3 hok6", "上堂": "soeng5 tong4", "落堂": "lok6 tong4", "做功課": "zou6 gung1 fo3", "考試": "haau2 si3",
    "開會": "hoi1 wui6", "加班": "gaa1 baan1", "請假": "cing2 gaa3",
    # 手机 / 沟通
    "打電話": "daa2 din6 waa2", "發信息": "faat3 seon3 sik1", "發短信": "faat3 dyun2 seon3", "發微信": "faat3 mei4 seon3", "覆信息": "fuk1 seon3 sik1",
    "上網": "soeng5 mong5", "玩手機": "waan2 sau2 gei1", "用手機": "jung6 sau2 gei1",
    # 医疗 / 住宿
    "睇醫生": "tai2 ji1 sang1", "去醫院": "heoi3 ji1 jyun2", "食藥": "sik6 joek6", "入住": "jap6 zyu6", "退房": "teoi3 fong2", "訂房": "deng6 fong2",
    # 语言学习
    "講粵語": "gong2 jyut6 jyu5", "學粵語": "hok6 jyut6 jyu5",
}
EXTRA_JP.update(SUPPLEMENT_JP)

# 第二轮查漏补缺词库：给新增日常短语固定粤拼，避免被拆成难读碎片。
AUDIT_JP = {
    "睇醫生": "tai2 ji1 sang1", "去睇醫生": "heoi3 tai2 ji1 sang1", "睇書": "tai2 syu1", "讀書": "duk6 syu1",
    "講嘢": "gong2 je5", "傾偈": "king1 gai2", "傾陣偈": "king1 zan6 gai2",
    "食嘢": "sik6 je5", "飲嘢": "jam2 je5", "肚餓": "tou5 ngo6", "我肚餓": "ngo5 tou5 ngo6", "口渴": "hau2 hot3",
    "煮飯": "zyu2 faan6", "煮餸": "zyu2 sung3", "買衫": "maai5 saam1", "平啲": "peng4 di1", "唔要辣": "m4 jiu3 laat6",
    "少冰": "siu2 bing1", "多冰": "do1 bing1", "拎走": "ling1 zau2", "外賣": "ngoi6 maai6",
    "搭車": "daap3 ce1", "地鐵站": "dei6 tit3 zaam6", "巴士站": "baa1 si6 zaam6", "去商場": "heoi3 soeng1 coeng4", "行商場": "haang4 soeng1 coeng4",
    "轉左": "zyun2 zo2", "轉右": "zyun2 jau6", "直行": "zik6 haang4",
    "叉電": "caa1 din6", "手機冇電": "sau2 gei1 mou5 din6", "網絡唔好": "mong5 lok3 m4 hou2", "網唔好": "mong5 m4 hou2",
    "搵唔到": "wan2 m4 dou2", "仲未": "zung6 mei6", "唔舒服": "m4 syu1 fuk6", "頭痛": "tau4 tung3", "發燒": "faat3 siu1", "咳": "kat1",
    "洗衫": "sai2 saam1", "一陣見": "jat1 zan6 gin3", "即刻返嚟": "zik1 hak1 faan1 lai4",
    # 上下文短语，解决同一个粤拼音节在不同词里中文译音不清楚的问题。
    "起身": "hei2 san1", "影相": "jing2 soeng2", "睇戲": "tai2 hei3", "去睇戲": "heoi3 tai2 hei3", "電影": "din6 jing2", "戲飛": "hei3 fei1",
}
EXTRA_JP.update(AUDIT_JP)

AUDIT_JP_FIXES = {
    "去睇書": "heoi3 tai2 syu1", "我唔舒服": "ngo5 m4 syu1 fuk6", "舒服": "syu1 fuk6",
    "買飛": "maai5 fei1", "車飛": "ce1 fei1", "外賣": "ngoi6 maai6", "退房": "teoi3 fong2", "入住": "jap6 zyu6",
    "去商場": "heoi3 soeng1 coeng4", "商場": "soeng1 coeng4", "酒店": "zau2 dim3", "機場": "gei1 coeng4", "車站": "ce1 zaam6",
}
EXTRA_JP.update(AUDIT_JP_FIXES)

AUDIT_JP_2 = {
    # 基础回应
    "拜拜": "baai1 baai3", "冇事": "mou5 si6", "冇問題": "mou5 man6 tai4", "唔得": "m4 dak1", "好呀": "hou2 aa3", "辛苦晒": "san1 fu2 saai3",
    # 餐饮
    "你食咗飯未": "nei5 sik6 zo2 faan6 mei6", "食咗飯未": "sik6 zo2 faan6 mei6", "食飽": "sik6 baau2", "食飽喇": "sik6 baau2 laa3", "我食飽喇": "ngo5 sik6 baau2 laa3",
    "我口渴": "ngo5 hau2 hot3", "口渴": "hau2 hot3", "我要食飯": "ngo5 jiu3 sik6 faan6", "我想食嘢": "ngo5 soeng2 sik6 je5",
    "可唔可以": "ho2 m4 ho2 ji5", "可唔可以拎走": "ho2 m4 ho2 ji5 ling1 zau2", "走冰": "zau2 bing1", "少辣": "siu2 laat6", "等位要幾耐": "dang2 wai2 jiu3 gei2 noi6",
    "有冇餐牌": "jau5 mou5 caan1 paai2", "有冇位": "jau5 mou5 wai2", "使唔使排隊": "sai2 m4 sai2 paai4 deoi6",
    # 购物/支付
    "可唔可以平啲": "ho2 m4 ho2 ji5 peng4 di1", "試吓": "si3 haa5", "我想試吓": "ngo5 soeng2 si3 haa5", "碌卡": "luk1 kaat1", "可唔可以碌卡": "ho2 m4 ho2 ji5 luk1 kaat1",
    "可唔可以掃碼": "ho2 m4 ho2 ji5 sou3 maa5", "有冇發票": "jau5 mou5 faat3 piu3", "發票": "faat3 piu3", "可唔可以開發票": "ho2 m4 ho2 ji5 hoi1 faat3 piu3", "退貨": "teoi3 fo3", "我要退貨": "ngo5 jiu3 teoi3 fo3",
    # 出行/方向
    "到咗未": "dou3 zo2 mei6", "蕩失路": "dong6 sat1 lou6", "我蕩失路": "ngo5 dong6 sat1 lou6", "搵唔到路": "wan2 m4 dou2 lou6", "路": "lou6",
    # 起居/学校
    "起身咗": "hei2 san1 zo2", "我起身咗": "ngo5 hei2 san1 zo2", "我頭先起身": "ngo5 tau4 sin1 hei2 san1", "我唔識寫": "ngo5 m4 sik1 se2", "唔識寫": "m4 sik1 se2",
    "我聽唔明": "ngo5 teng1 m4 ming4", "聽唔明": "teng1 m4 ming4", "唔該再講多次": "m4 goi1 zoi3 gong2 do1 ci3", "再講多次": "zoi3 gong2 do1 ci3", "講慢少少": "gong2 maan6 siu2 siu2",
    "我要返學": "ngo5 jiu3 faan1 hok6", "要返學": "jiu3 faan1 hok6", "我要返工": "ngo5 jiu3 faan1 gung1", "要返工": "jiu3 faan1 gung1", "我要放工": "ngo5 jiu3 fong3 gung1",
    # 工作/状态
    "遲到咗": "ci4 dou3 zo2", "我遲到咗": "ngo5 ci4 dou3 zo2", "今日好忙": "gam1 jat6 hou2 mong4", "好忙": "hou2 mong4", "我喺屋企": "ngo5 hai2 uk1 kei5", "忙唔忙": "mong4 m4 mong4", "你而家忙唔忙": "nei5 ji4 gaa1 mong4 m4 mong4",
    # 医疗/求助
    "肚痛": "tou5 tung3", "我肚痛": "ngo5 tou5 tung3", "牙痛": "ngaa4 tung3", "我牙痛": "ngo5 ngaa4 tung3", "救命": "gau3 meng6", "急救": "gap1 gau3", "打急救電話": "daa2 gap1 gau3 din6 waa2", "藥房": "joek6 fong2",
    # 酒店/设施
    "我訂咗房": "ngo5 deng6 zo2 fong2", "有冇房": "jau5 mou5 fong2", "房幾多錢": "fong2 gei2 do1 cin2", "換房": "wun6 fong2", "我要換房": "ngo5 jiu3 wun6 fong2", "冷氣": "laang5 hei3", "冷氣壞咗": "laang5 hei3 waai6 zo2", "熱水": "jit6 seoi2",
    # 手机/网络
    "無線網絡": "mou4 sin3 mong5 lok3", "有冇無線網絡": "jau5 mou5 mou4 sin3 mong5 lok3", "密碼": "mat6 maa5", "密碼係咩": "mat6 maa5 hai6 me1", "上唔到網": "soeng5 m4 dou2 mong5", "我上唔到網": "ngo5 soeng5 m4 dou2 mong5", "搞掂": "gaau2 dim6", "搞掂咗": "gaau2 dim6 zo2",
    # 娱乐/天气
    "可唔可以影相": "ho2 m4 ho2 ji5 jing2 soeng2", "幫我影相": "bong1 ngo5 jing2 soeng2", "等我陣": "dang2 ngo5 zan6", "你等我陣": "nei5 dang2 ngo5 zan6", "今日好凍": "gam1 jat6 hou2 dung3", "好凍": "hou2 dung3", "落雨喇": "lok6 jyu5 laa3", "帶遮": "daai3 ze1",
    "我識少少粵語": "ngo5 sik1 siu2 siu2 jyut6 jyu5", "我唔識粵語": "ngo5 m4 sik1 jyut6 jyu5",
}
EXTRA_JP.update(AUDIT_JP_2)
# 避免超长整句压缩成一张卡，保留为自然词组卡。
EXTRA_JP.pop("我哋去睇戲啦", None)
JP_RE = re.compile(r"^([a-z]+)([1-6])$")
CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
CJK_GLOBAL_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
PUNCT = set("，。！？；：、,.!?;:（）()【】[]《》<>“”‘’\"'")


def load_opencc_s2t() -> tuple[dict[str, str], dict[str, str], int]:
    try:
        data = json.loads(S2T_OPENCC_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}, {}, 1
    chars = data.get("chars", {})
    phrases = data.get("phrases", {})
    max_len = int(data.get("meta", {}).get("max_phrase_length", 1))
    return chars, phrases, max_len


S2T_CHARS, S2T_PHRASES, S2T_MAX_PHRASE_LEN = load_opencc_s2t()


def simple_to_traditional(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        found = None
        limit = min(S2T_MAX_PHRASE_LEN, len(text) - i)
        for size in range(limit, 1, -1):
            piece = text[i:i + size]
            value = S2T_PHRASES.get(piece)
            if value:
                found = (value, size)
                break
        if found:
            out.append(found[0])
            i += found[1]
            continue
        ch = text[i]
        out.append(S2T_CHARS.get(ch, ch.translate(S2T)))
        i += 1
    return "".join(out)



def read_user_lexicon() -> dict[str, str]:
    custom: dict[str, str] = {}
    try:
        USER_LEXICON_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not USER_LEXICON_PATH.exists():
            USER_LEXICON_PATH.write_text("# 每行一个补充词：粤语词=jyutping\n# 例：新詞=san1 ci4\n", encoding="utf-8")
        lines = USER_LEXICON_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return custom
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        word, jp = [part.strip() for part in line.split("=", 1)]
        if word and all(JP_RE.match(item) for item in jp.split()):
            custom[word] = jp
    return custom


def append_user_lexicon(word: str, jp: str) -> None:
    USER_LEXICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USER_LEXICON_PATH.exists():
        USER_LEXICON_PATH.write_text("# 每行一个补充词：粤语词=jyutping\n", encoding="utf-8")
    with USER_LEXICON_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{word}={jp}\n")


def load_history() -> list[dict[str, object]]:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not HISTORY_PATH.exists():
            return []
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            text_value = str(item.get("text", "")).strip()
            if not text_value or text_value in seen:
                continue
            seen.add(text_value)
            records.append({
                "text": text_value,
                "cantonese": str(item.get("cantonese", "")),
                "ts": int(float(item.get("ts", 0) or 0)),
            })
    records.sort(key=lambda item: int(item.get("ts", 0)), reverse=True)
    return records[:2000]


def save_history(records: list[dict[str, object]]) -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps(records[:2000], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def add_history_record(records: list[dict[str, object]], text_value: str, cantonese: str) -> list[dict[str, object]]:
    text_value = text_value.strip()
    if not text_value:
        return records
    now = int(time.time())
    new_records = [item for item in records if str(item.get("text", "")).strip() != text_value]
    new_records.insert(0, {"text": text_value, "cantonese": cantonese, "ts": now})
    return new_records[:2000]


def history_time_label(ts: int) -> str:
    if not ts:
        return ""
    now = int(time.time())
    diff = max(0, now - ts)
    if diff < 3600:
        minutes = max(1, diff // 60)
        return f"{minutes}分钟前"
    if diff < 86400:
        return f"{diff // 3600}小时前"
    if diff < 7 * 86400:
        return f"{diff // 86400}天前"
    return time.strftime("%m-%d", time.localtime(ts))

def load_lexicon() -> tuple[dict[str, str], int, int]:
    data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    entries = data["entries"]
    entries.update(EXTRA_JP)
    entries.update(read_user_lexicon())
    max_len = max(int(data["meta"].get("max_word_length", 12)), max(map(len, EXTRA_JP)))
    count = len(entries)
    return entries, max_len, count


LEXICON, MAX_WORD_LEN, ENTRY_COUNT = load_lexicon()


def is_cjk(char: str) -> bool:
    return bool(CJK_RE.match(char))


def translate_to_cantonese(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            out.append(ch)
            i += 1
            continue
        matched = False
        for src, dst in RULE_LIST:
            if text.startswith(src, i):
                out.append(dst)
                i += len(src)
                matched = True
                break
        if matched:
            continue
        out.append(simple_to_traditional(ch))
        i += 1
    result = simple_to_traditional("".join(out))
    result = result.replace("唔係咗", "唔係")
    result = result.replace("係咗", "係")
    # OpenCC 会把口语字“吓”转成“嚇”，这里恢复成粤语口语写法。
    result = result.replace("試嚇", "試吓")
    return result


def lookup(text: str) -> tuple[str, str] | None:
    if text in LEXICON:
        return text, LEXICON[text]
    converted = simple_to_traditional(text)
    if converted in LEXICON:
        return converted, LEXICON[converted]
    return None


def segment(text: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in PUNCT:
            result.append({"word": ch, "jp": "", "kind": "punct"})
            i += 1
            continue
        if not is_cjk(ch):
            j = i + 1
            while j < len(text) and not text[j].isspace() and not is_cjk(text[j]) and text[j] not in PUNCT:
                j += 1
            result.append({"word": text[i:j], "jp": "", "kind": "plain"})
            i = j
            continue
        best = None
        limit = min(MAX_WORD_LEN, len(text) - i)
        for size in range(limit, 0, -1):
            piece = text[i:i + size]
            if not all(is_cjk(c) for c in piece):
                continue
            found = lookup(piece)
            if found:
                best = (piece, found[1], size)
                break
        if best:
            word, jp, size = best
            result.append({"word": word, "jp": jp, "kind": "known"})
            i += size
        else:
            result.append({"word": ch, "jp": "?", "kind": "unknown"})
            i += 1
    return result


def split_jp(jp: str) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    for raw in jp.split():
        m = JP_RE.match(raw)
        if m:
            parts.append((m.group(1), m.group(2)))
        elif raw == "?":
            parts.append(("?", ""))
    return parts


def jyutping_with_marks(jp: str, *, joiner: str = " ") -> str:
    parts = []
    for base, num in split_jp(jp):
        if base == "?":
            parts.append("?")
        else:
            parts.append(f"{base}{TONE_BADGE.get(num, '')}")
    return joiner.join(parts)


def linear(tokens: list[dict[str, str]]) -> str:
    chunks = []
    for token in tokens:
        word, jp = token["word"], token["jp"]
        if not jp:
            chunks.append(word)
        elif jp == "?":
            chunks.append(f"{word}(未收录)")
        else:
            chunks.append(f"{word}({jyutping_with_marks(jp)})")
    # / 表示卡片之间可以短暂停顿；同一括号内就是一组连读。
    return " / ".join(chunks)



CHINESE_SOUND_HINTS = {
    # 高频完整音节：优先用一个普通话近似字，避免“声母+韵母”拼成两个字导致难连读。
    "ngo": "鹅", "nei": "内", "hou": "猴", "soeng": "上", "heoi": "虚", "sik": "食", "faan": "饭",
    "hok": "学", "haau": "校", "tou": "图", "syu": "书", "gun": "馆", "bin": "边", "dou": "度",
    "hai": "系", "gaa": "家", "gei": "几", "do": "多", "cin": "钱", "jat": "日", "gam": "甘",
    "uk": "屋", "kei": "企", "go": "个", "baa": "巴", "si": "时", "jam": "饮", "caa": "茶",
    "m": "唔", "goi": "该", "ze": "谢", "saai": "晒", "zung": "钟", "ji": "意", "gong": "讲",
    "tai": "睇", "gin": "见", "zou": "做", "je": "夜", "fan": "芬", "gaau": "交", "lai": "嚟",
    "gwong": "广", "zau": "就", "jyut": "月", "jyu": "鱼", "maan": "慢", "zik": "即", "hak": "刻",
    "dak": "得", "jau": "有", "mou": "冇", "ho": "可", "sai": "使", "liu": "了", "laa": "啦",

    # 解决“鸡腿”等两字词：一个音节只给一个近似字。
    "gai": "该", "teoi": "推", "jik": "亦", "juk": "肉", "siu": "烧", "zaa": "炸", "paa": "扒",
    "fan": "芬", "gaau": "交", "maan": "慢", "dim": "点", "kam": "琴", "je": "夜", "seng": "醒", "zoek": "着",
    "gaai": "街", "dim": "点", "joeng": "样", "ting": "听", "cam": "寻", "tau": "头", "sin": "先", "zan": "真",
    "keoi": "佢", "di": "啲", "ge": "嘅", "zo": "咗", "me": "咩", "waa": "话", "bei": "畀", "tung": "同",
    "bong": "帮", "sau": "手", "gan": "紧", "jiu": "要", "deoi": "对", "zyu": "住", "zi": "知", "ming": "明",
    "giu": "叫", "meng": "名", "wui": "会", "tit": "铁", "dik": "的", "daap": "搭", "coeng": "场", "ce": "车",
    "zaam": "站", "ci": "厕", "so": "所", "caan": "餐", "paai": "牌", "maai": "买", "daan": "单", "ling": "拎",
    "ngoi": "爱", "naan": "难", "gwai": "贵", "peng": "平", "taai": "太", "hoi": "开", "sam": "心", "nau": "嬲",
    "gui": "攰", "mong": "忙", "leng": "靓", "lei": "利", "cai": "齐", "dang": "等", "wun": "碗", "se": "些",
    # 常用兜底音节，也必须一个粤拼音节只对应一个中文译音字。
    "maa": "妈", "naa": "拿", "laai": "赖", "laam": "蓝", "naam": "南", "ngaa": "牙", "ngan": "银", "ngau": "牛",
    "waa": "哇", "wai": "威", "wan": "温", "wang": "宏", "wat": "屈", "wing": "荣", "wong": "王", "wut": "活",
    "baa": "巴", "bai": "拜", "ban": "斌", "bat": "不", "bek": "逼", "beng": "饼", "bik": "碧", "bin": "边", "bit": "必", "bo": "波", "bok": "博", "bong": "帮", "bou": "宝", "bui": "杯", "bun": "本", "bung": "崩",
    "paa": "趴", "pai": "派", "pan": "喷", "pat": "匹", "pek": "劈", "peng": "平", "pik": "匹", "pin": "篇", "pit": "撇", "po": "婆", "pok": "扑", "pong": "旁", "pou": "抱", "pui": "配", "pun": "盘",
    "faa": "花", "fai": "辉", "fan": "芬", "fat": "佛", "fei": "飞", "fik": "飞", "fin": "翩", "fo": "科", "fok": "霍", "fong": "方", "fu": "夫", "fui": "灰", "fun": "欢", "fung": "风",
    "daa": "打", "dai": "低", "dam": "担", "dan": "登", "dap": "搭", "dat": "达", "dei": "地", "dek": "的", "deng": "定", "dik": "的", "din": "电", "dip": "碟", "dit": "跌", "doe": "朵", "dong": "当", "duk": "独", "dung": "东",
    "taa": "他", "tai": "睇", "tam": "探", "tan": "吞", "tap": "塔", "tat": "挞", "tek": "踢", "teng": "听", "tik": "踢", "tin": "天", "tip": "贴", "tit": "铁", "tong": "汤", "tuk": "秃", "tung": "同",
    "gaa": "家", "gaai": "街", "gaam": "监", "gaan": "间", "gaap": "甲", "gaat": "扎", "gaau": "交", "gai": "该", "gam": "甘", "gan": "根", "gap": "急", "gat": "吉", "ge": "嘅", "gei": "几", "geng": "颈", "gik": "激", "gin": "见", "gip": "劫", "git": "结", "go": "个", "goek": "脚", "goeng": "姜", "goi": "该", "gok": "国", "gong": "讲", "gou": "高", "gu": "姑", "guk": "谷", "gun": "馆", "gung": "工",
    "kaa": "卡", "kaai": "楷", "kaam": "琴", "kaan": "刊", "kaap": "卡", "kaat": "咭", "kaau": "靠", "kai": "溪", "kam": "琴", "kan": "勤", "kap": "及", "kat": "咳", "kei": "企", "keng": "倾", "kik": "剧", "kin": "乾", "kit": "揭", "koek": "却", "koeng": "强", "koi": "盖", "kok": "确", "kong": "抗", "ku": "箍", "kuk": "曲", "kung": "穷",
    "haa": "哈", "haai": "鞋", "haam": "咸", "haan": "闲", "haap": "侠", "haat": "吓", "haau": "校", "hai": "系", "ham": "含", "han": "痕", "hap": "合", "hat": "核", "hei": "戏", "hek": "吃", "heng": "轻", "him": "谦", "hin": "显", "hip": "协", "hit": "歇", "ho": "可", "hoe": "靴", "hoeng": "香", "hoi": "开", "hok": "学", "hon": "寒", "hong": "康", "huk": "哭", "hung": "红",
    "zaa": "渣", "zaai": "债", "zaam": "站", "zaan": "赞", "zaap": "集", "zaat": "扎", "zaau": "找", "zai": "仔", "zam": "针", "zan": "真", "zap": "执", "zat": "质", "ze": "谢", "zek": "只", "zeng": "正", "zeoi": "最", "zeon": "进", "zeot": "卒", "zi": "知", "zik": "即", "zim": "尖", "zin": "煎", "zip": "接", "zit": "节", "zo": "咗", "zoek": "着", "zoeng": "章", "zoi": "再", "zok": "作", "zong": "装", "zou": "做", "zuk": "足", "zung": "钟", "zyu": "住", "zyun": "转", "zyut": "绝",
    "caa": "茶", "caai": "猜", "caam": "惨", "caan": "餐", "caap": "插", "caat": "擦", "caau": "抄", "cai": "齐", "cam": "寻", "can": "亲", "cap": "缉", "cat": "七", "ce": "车", "cek": "赤", "ceng": "青", "ceoi": "吹", "ceon": "春", "ceot": "出", "ci": "痴", "cik": "斥", "cim": "签", "cin": "钱", "cip": "妾", "cit": "切", "co": "初", "coek": "桌", "coeng": "场", "coi": "菜", "cok": "错", "cong": "仓", "cou": "粗", "cuk": "促", "cung": "从", "cyu": "厨", "cyun": "村", "cyut": "撮",
    "saa": "沙", "saai": "晒", "saam": "三", "saan": "山", "saap": "萨", "saat": "杀", "saau": "梢", "sai": "使", "sam": "心", "san": "新", "sap": "十", "sat": "实", "se": "些", "sek": "锡", "seng": "醒", "seoi": "水", "seon": "信", "seot": "术", "si": "时", "sik": "食", "sim": "闪", "sin": "先", "sip": "摄", "sit": "泄", "so": "所", "soe": "靴", "soeng": "上", "soi": "腮", "sok": "索", "song": "桑", "sou": "苏", "suk": "叔", "sung": "送", "syu": "书", "syun": "酸", "syut": "雪",
    "jaa": "也", "jaam": "淹", "jaan": "因", "jaap": "入", "jaat": "日", "jaau": "休", "jai": "制", "jam": "饮", "jan": "人", "jap": "入", "jat": "日", "je": "夜", "jek": "亦", "jeng": "赢", "jing": "英", "jeoi": "锐", "jeon": "润", "jeot": "乙", "ji": "意", "jik": "亦", "jim": "严", "jin": "言", "jip": "叶", "jit": "热", "joek": "约", "joeng": "样", "joi": "哉", "juk": "肉", "jung": "用", "jyu": "鱼", "jyun": "元", "jyut": "月",
}
CHINESE_SOUND_HINTS.update({
    # 娱乐 / 日常新增音节，一个粤拼音节只给一个中文译音字。
    "hei": "希", "bou": "煲", "kek": "剧", "bo": "播", "pin": "片", "caat": "刷", "san": "新", "man": "闻",
    "teng": "听", "ngok": "乐", "coeng": "唱", "jing": "英", "paak": "拍", "soeng": "上",
    "haang": "行", "lok": "落", "ce": "车", "piu": "票", "sung": "餸", "wai": "位", "deng": "订",
    "zou": "早", "aan": "晏", "siu": "宵", "seoi": "水", "fe": "啡", "naai": "奶", "zau": "酒",
    "cung": "冲", "loeng": "凉", "min": "面", "ngaa": "牙", "tong": "堂", "gung": "功", "fo": "课",
    "haau": "考", "wui": "会", "cing": "请", "seon": "信", "dyun": "短", "mei": "微", "fuk": "覆", "mong": "网", "waan": "玩", "jung": "用",
    "sang": "生", "jyun": "院", "joek": "药", "jap": "入", "zyu": "住", "fong": "房", "jyu": "语",
})

CHINESE_SOUND_HINTS_AUDIT_2 = {
    "baai": "拜", "mut": "没", "baau": "饱", "hot": "渴", "laat": "辣", "bing": "冰", "gau": "救", "ni": "呢", "faat": "发",
    "mai": "迷", "lou": "路", "wui": "会", "kui": "会", "ding": "订", "hung": "空", "tiu": "调", "waai": "坏", "mat": "密", "ging": "经",
    "laang": "冷", "daai": "带", "saan": "伞", "noi": "耐", "luk": "碌", "dong": "荡", "sat": "失", "gap": "急", "wun": "换",
    "ze": "遮", "jyu": "雨", "aa": "呀", "fo": "货", "fong": "房", "fuk": "服", "syu": "书", "duk": "读", "king": "倾",
}
CHINESE_SOUND_HINTS.update(CHINESE_SOUND_HINTS_AUDIT_2)

# 词级中文译音：同一个粤拼音节在不同词里可能需要不同的中文提示。
# 仍然保持“一音节一个中文译音字”，只是按整个词替换，方便连读。
CHINESE_PHRASE_SOUND_HINTS = {
    "睇戲": "睇ˊ戏", "去睇戲": "虚睇ˊ戏", "戲飛": "戏飞ˉ", "電影": "电ˍ英ˊ", "睇電視": "睇ˊ电ˍ视ˍ", "煲劇": "煲ˉ剧ˍ",
    "睇直播": "睇ˊ直ˍ播", "睇片": "睇ˊ片ˊ", "刷片": "刷片ˊ", "睇新聞": "睇ˊ新ˉ闻ˋ", "聽歌": "听ˉ歌ˉ", "聽音樂": "听ˉ音ˉ乐ˍ",
    "影相": "英ˊ相ˊ", "拍片": "拍片ˊ",
    "雞腿": "该ˉ推ˊ", "雞翼": "该ˉ亦ˍ", "雞肉": "该ˉ肉ˍ", "燒雞": "烧ˉ该ˉ", "炸雞": "炸ˋ该ˉ", "雞扒": "该ˉ扒ˊ",
    "瞓覺": "芬交", "去瞓覺": "虚芬交", "我瞓覺": "鹅ˇ芬交", "我要瞓覺": "鹅ˇ要芬交", "我想瞓覺": "鹅ˇ上ˊ芬交",
    "瞓醒": "芬醒ˊ", "瞓唔著": "芬唔ˋ着ˍ", "我瞓唔著": "鹅ˇ芬唔ˋ着ˍ", "起身": "起ˊ身ˉ",
    "去廁所": "虚厕所ˊ", "沖涼": "冲ˉ凉ˋ", "洗頭": "洗ˊ头ˋ", "洗面": "洗ˊ面ˍ", "刷牙": "刷牙ˋ", "洗衫": "洗ˊ衫ˉ",
    "睇醫生": "睇ˊ医ˉ生ˉ", "去睇醫生": "虚睇ˊ医ˉ生ˉ", "去醫院": "虚医ˉ院ˊ", "食藥": "食ˍ药ˍ", "唔舒服": "唔ˋ书ˉ服ˍ", "頭痛": "头ˋ痛", "發燒": "发烧ˉ", "咳": "咳ˉ",
    "行街": "行ˋ街ˉ", "行商場": "行ˋ商ˉ场ˋ", "搭巴士": "搭巴ˉ士ˍ", "搭地鐵": "搭地ˍ铁", "搭的士": "搭的ˉ士ˊ", "搭車": "搭车ˉ",
    "地鐵站": "地ˍ铁站ˍ", "巴士站": "巴ˉ士ˍ站ˍ", "落車": "落ˍ车ˉ", "上車": "上ˇ车ˉ", "轉左": "转ˊ左ˊ", "轉右": "转ˊ右ˍ", "直行": "直ˍ行ˋ",
    "買嘢": "买ˇ嘢ˇ", "買餸": "买ˇ餸", "買衫": "买ˇ衫ˉ", "落單": "落ˍ单ˉ", "點菜": "点ˊ菜", "畀錢": "畀ˊ钱ˊ", "埋單": "埋ˋ单ˉ",
    "食早餐": "食ˍ早ˊ餐ˉ", "食晏": "食ˍ晏", "食晚飯": "食ˍ慢ˇ饭ˍ", "食宵夜": "食ˍ宵ˉ夜ˍ", "食嘢": "食ˍ嘢ˇ", "飲嘢": "饮ˊ嘢ˇ",
    "飲水": "饮ˊ水ˊ", "飲咖啡": "饮ˊ咖啡ˉ", "飲奶茶": "饮ˊ奶ˇ茶ˋ", "飲酒": "饮ˊ酒ˊ", "肚餓": "肚ˇ饿ˍ", "口渴": "口ˊ渴",
    "煮飯": "煮ˊ饭ˍ", "煮餸": "煮ˊ餸", "平啲": "平ˋ啲ˉ", "唔要辣": "唔ˋ要辣ˍ", "少冰": "少ˊ冰ˉ", "多冰": "多ˉ冰ˉ", "拎走": "拎ˉ走ˊ",
    "返學": "返ˉ学ˍ", "放學": "放学ˍ", "上堂": "上ˇ堂ˋ", "落堂": "落ˍ堂ˋ", "做功課": "做ˍ功ˉ课", "考試": "考ˊ试",
    "開會": "开ˉ会ˍ", "加班": "加ˉ班ˉ", "請假": "请ˊ假", "返工": "返ˉ工ˉ", "放工": "放工ˉ",
    "打電話": "打ˊ电ˍ话ˊ", "發信息": "发信ˉ息ˉ", "發短信": "发短ˊ信", "發微信": "发微ˋ信", "覆信息": "覆ˉ信息ˉ",
    "上網": "上ˇ网ˇ", "玩手機": "玩ˊ手ˊ机ˉ", "用手機": "用ˍ手ˊ机ˉ", "叉電": "叉ˉ电ˍ", "手機冇電": "手ˊ机ˉ冇ˇ电ˍ", "網絡唔好": "网ˇ落唔ˋ好ˊ", "網唔好": "网ˇ唔ˋ好ˊ",
    "講粵語": "讲ˊ月ˍ语ˇ", "學粵語": "学ˍ月ˍ语ˇ", "講嘢": "讲ˊ嘢ˇ", "傾偈": "倾ˉ计ˊ", "傾陣偈": "倾ˉ阵ˍ计ˊ",
    "搵唔到": "温ˊ唔ˋ到ˊ", "仲未": "中ˍ未ˍ", "一陣見": "一ˉ阵ˍ见", "即刻返嚟": "即ˉ刻ˉ返ˉ嚟ˋ",
}
CHINESE_PHRASE_SOUND_HINTS.update({
    # 二轮截图/语料检查发现的上下文修正。
    "去商場": "虚商ˉ场ˋ", "商場": "商ˉ场ˋ", "我肚餓": "鹅ˇ肚ˇ饿ˍ", "退房": "退房ˊ", "入住": "入ˍ住ˍ",
    "我唔舒服": "鹅ˇ唔ˋ书ˉ服ˍ", "舒服": "书ˉ服ˍ", "去睇書": "虚睇ˊ书ˉ", "買飛": "买ˇ飞ˉ", "車飛": "车ˉ飞ˉ",
    "外賣": "外ˍ卖ˍ", "酒店": "酒ˊ店", "機場": "机ˉ场ˋ", "車站": "车ˉ站ˍ", "廁所": "厕所ˊ",
})

CHINESE_PHRASE_SOUND_HINTS_AUDIT_2 = {
    "拜拜": "拜ˉ拜", "冇事": "冇ˇ事ˍ", "冇問題": "冇ˇ问ˍ题ˋ", "唔得": "唔ˋ得ˉ", "好呀": "好ˊ呀", "辛苦晒": "辛ˉ苦ˊ晒",
    "你食咗飯未": "内ˇ食ˍ咗ˊ饭ˍ未ˍ", "食咗飯未": "食ˍ咗ˊ饭ˍ未ˍ", "我食飽喇": "鹅ˇ食ˍ饱ˊ喇", "食飽喇": "食ˍ饱ˊ喇",
    "我口渴": "鹅ˇ口ˊ渴", "口渴": "口ˊ渴", "我要食飯": "鹅ˇ要食ˍ饭ˍ", "我想食嘢": "鹅ˇ上ˊ食ˍ嘢ˇ", "可唔可以": "可ˊ唔ˋ可ˊ意ˇ",
    "可唔可以拎走": "可ˊ唔ˋ可ˊ意ˇ拎ˉ走ˊ", "走冰": "走ˊ冰ˉ", "少辣": "少ˊ辣ˍ", "等位要幾耐": "等ˊ位ˊ要几ˊ耐ˍ", "有冇餐牌": "有ˇ冇ˇ餐ˉ牌ˊ",
    "有冇位": "有ˇ冇ˇ位ˊ", "使唔使排隊": "使ˊ唔ˋ使ˊ排ˋ队ˍ", "可唔可以平啲": "可ˊ唔ˋ可ˊ意ˇ平ˋ啲ˉ", "試吓": "试吓ˇ", "我想試吓": "鹅ˇ上ˊ试吓ˇ",
    "碌卡": "碌ˉ卡ˉ", "可唔可以碌卡": "可ˊ唔ˋ可ˊ意ˇ碌ˉ卡ˉ", "可唔可以掃碼": "可ˊ唔ˋ可ˊ意ˇ扫码ˇ", "有冇發票": "有ˇ冇ˇ发票", "發票": "发票",
    "可唔可以開發票": "可ˊ唔ˋ可ˊ意ˇ开ˉ发票", "退貨": "退货", "我要退貨": "鹅ˇ要退货", "到咗未": "到咗ˊ未ˍ", "蕩失路": "荡ˍ失ˉ路ˍ", "我蕩失路": "鹅ˇ荡ˍ失ˉ路ˍ", "搵唔到路": "温ˊ唔ˋ到ˊ路ˍ",
    "起身咗": "起ˊ身ˉ咗ˊ", "我起身咗": "鹅ˇ起ˊ身ˉ咗ˊ", "我頭先起身": "鹅ˇ头ˋ先ˉ起ˊ身ˉ", "我唔識寫": "鹅ˇ唔ˋ识ˉ写ˊ", "唔識寫": "唔ˋ识ˉ写ˊ",
    "我聽唔明": "鹅ˇ听ˉ唔ˋ明ˋ", "聽唔明": "听ˉ唔ˋ明ˋ", "唔該再講多次": "唔ˋ该ˉ再讲ˊ多ˉ次", "再講多次": "再讲ˊ多ˉ次", "講慢少少": "讲ˊ慢ˍ少ˊ少ˊ",
    "我要返學": "鹅ˇ要返ˉ学ˍ", "要返學": "要返ˉ学ˍ", "我要返工": "鹅ˇ要返ˉ工ˉ", "要返工": "要返ˉ工ˉ", "我要放工": "鹅ˇ要放工ˉ",
    "遲到咗": "迟ˋ到咗ˊ", "我遲到咗": "鹅ˇ迟ˋ到咗ˊ", "今日好忙": "甘ˉ日ˍ好ˊ忙ˋ", "好忙": "好ˊ忙ˋ", "我喺屋企": "鹅ˇ系ˊ屋ˉ企ˇ", "忙唔忙": "忙ˋ唔ˋ忙ˋ", "你而家忙唔忙": "内ˇ意ˋ家ˉ忙ˋ唔ˋ忙ˋ",
    "肚痛": "肚ˇ痛", "我肚痛": "鹅ˇ肚ˇ痛", "牙痛": "牙ˋ痛", "我牙痛": "鹅ˇ牙ˋ痛", "救命": "救名ˍ", "急救": "急ˉ救", "打急救電話": "打ˊ急ˉ救电ˍ话ˊ", "藥房": "药ˍ房ˊ",
    "我訂咗房": "鹅ˇ订ˍ咗ˊ房ˊ", "有冇房": "有ˇ冇ˇ房ˊ", "房幾多錢": "房ˊ几ˊ多ˉ钱ˊ", "換房": "换ˍ房ˊ", "我要換房": "鹅ˇ要换ˍ房ˊ", "冷氣": "冷ˇ气", "冷氣壞咗": "冷ˇ气坏ˍ咗ˊ", "熱水": "热ˍ水ˊ",
    "無線網絡": "无ˋ线网ˇ落", "有冇無線網絡": "有ˇ冇ˇ无ˋ线网ˇ落", "密碼": "密ˍ码ˇ", "密碼係咩": "密ˍ码ˇ系ˍ咩ˉ", "上唔到網": "上ˇ唔ˋ到ˊ网ˇ", "我上唔到網": "鹅ˇ上ˇ唔ˋ到ˊ网ˇ", "搞掂": "搞ˊ点ˍ", "搞掂咗": "搞ˊ点ˍ咗ˊ",
    "可唔可以影相": "可ˊ唔ˋ可ˊ意ˇ英ˊ相ˊ", "幫我影相": "帮ˉ鹅ˇ英ˊ相ˊ", "等我陣": "等ˊ鹅ˇ阵ˍ", "你等我陣": "内ˇ等ˊ鹅ˇ阵ˍ", "今日好凍": "甘ˉ日ˍ好ˊ冻", "好凍": "好ˊ冻", "落雨喇": "落ˍ雨ˇ喇", "帶遮": "带遮ˉ",
    "我識少少粵語": "鹅ˇ识ˉ少ˊ少ˊ月ˍ语ˇ", "我唔識粵語": "鹅ˇ唔ˋ识ˉ月ˍ语ˇ",
}
CHINESE_PHRASE_SOUND_HINTS.update(CHINESE_PHRASE_SOUND_HINTS_AUDIT_2)

INITIAL_SOUND_HINT = {
    "b": "巴", "p": "趴", "m": "妈", "f": "花", "d": "打", "t": "他", "n": "拿", "l": "拉",
    "g": "家", "k": "卡", "ng": "嗯", "h": "哈", "gw": "瓜", "kw": "夸", "w": "哇",
    "z": "知", "c": "痴", "s": "思", "j": "衣", "": "",
}
FINAL_SOUND_HINT = {
    "aa": "啊", "aai": "挨", "aau": "拗", "aam": "啱", "aan": "安", "aang": "盎", "aap": "鸭", "aat": "压", "aak": "额",
    "ai": "矮", "au": "欧", "am": "暗", "an": "恩", "ang": "庚", "ap": "噏", "at": "甩", "ak": "厄",
    "e": "诶", "ei": "诶", "eu": "欧", "em": "唔", "eng": "英", "ek": "吃",
    "i": "衣", "iu": "妖", "im": "严", "in": "烟", "ing": "英", "ip": "叶", "it": "热", "ik": "益",
    "o": "哦", "oi": "哀", "ou": "奥", "on": "安", "ong": "昂", "ot": "渴", "ok": "恶",
    "oe": "靴", "oeng": "央", "oek": "约", "eoi": "虚", "eon": "津", "eot": "卒",
    "u": "乌", "ui": "灰", "un": "碗", "ung": "翁", "ut": "活", "uk": "屋",
    "yu": "于", "yun": "晕", "yut": "月", "m": "唔", "ng": "嗯",
}


def one_cjk_or_base(text: str, base: str) -> str:
    """硬规则：一个粤拼音节最多显示一个中文译音字。"""
    chars = CJK_GLOBAL_RE.findall(text)
    if len(chars) <= 1:
        return text
    return chars[0] if chars else base


def chinese_sound_for_base(base: str) -> str:
    if base in CHINESE_SOUND_HINTS:
        return one_cjk_or_base(CHINESE_SOUND_HINTS[base], base)
    initial, final = split_initial_final(base)
    if initial == "" and final in FINAL_SOUND_HINT:
        return one_cjk_or_base(FINAL_SOUND_HINT[final], base)
    # 禁止再把声母+韵母拼成两个中文字，例如 maa 不能变成“妈啊”。
    # 未收录的音节先显示粤拼本身，等补词库。
    return base


def chinese_sound_for_jp(jp: str, *, with_tone_name: bool = False, joiner: str = " ") -> str:
    parts = []
    for base, num in split_jp(jp):
        if base == "?":
            parts.append("?")
        else:
            sound = chinese_sound_for_base(base)
            if with_tone_name and num in TONE:
                parts.append(f"{sound}{TONE_BADGE.get(num, num)} {TONE[num]['name']}")
            else:
                parts.append(f"{sound}{TONE_BADGE.get(num, num)}" if num else sound)
    return joiner.join(parts)


def chinese_sound_for_token(word: str, jp: str, *, with_tone_name: bool = False, joiner: str = " ") -> str:
    """中文译音优先用词级提示；教学细节仍可回到逐音节。"""
    if not with_tone_name:
        phrase_sound = CHINESE_PHRASE_SOUND_HINTS.get(word)
        if phrase_sound:
            return phrase_sound
    return chinese_sound_for_jp(jp, with_tone_name=with_tone_name, joiner=joiner)


def assert_phrase_sound_shapes() -> None:
    for word, sound in CHINESE_PHRASE_SOUND_HINTS.items():
        jp = LEXICON.get(word, "")
        if not jp:
            continue
        syllable_count = len(split_jp(jp))
        cjk_count = len(CJK_GLOBAL_RE.findall(sound))
        assert cjk_count <= syllable_count, f"{word}: {sound} has {cjk_count}>{syllable_count} CJK hints"
        assert not re.search(r"[1-6]", sound), f"{word}: tone digit leaked into {sound}"


def assert_no_double_chinese_sound(jp: str) -> None:
    for base, _num in split_jp(jp):
        if base == "?":
            continue
        sound = chinese_sound_for_base(base)
        assert len(CJK_GLOBAL_RE.findall(sound)) <= 1, f"{base} -> {sound}"


def sound_line(tokens: list[dict[str, str]]) -> str:
    chunks = []
    for token in tokens:
        jp = token.get("jp", "")
        if not jp:
            chunks.append(token.get("word", ""))
        elif jp == "?":
            chunks.append(f"{token.get('word', '')}(未收录)")
        else:
            chunks.append(chinese_sound_for_token(token.get("word", ""), jp, joiner=""))
    return " / ".join(chunks)


def compact_text_len(text: str) -> int:
    """估算显示宽度：中文算 2，英文/符号算 1，用于自动缩字号。"""
    score = 0
    for ch in str(text or ""):
        if ch.isspace():
            continue
        score += 2 if CJK_GLOBAL_RE.match(ch) else 1
    return score


def auto_font_size(text: str, *, base: int, min_size: int, ideal: int, step_chars: int = 4) -> int:
    extra = max(0, compact_text_len(text) - ideal)
    shrink = (extra + step_chars - 1) // step_chars
    return max(min_size, base - shrink)


def component_voice_text(kind: str, value: str, fallback: str = "") -> str:
    if kind == "initial":
        return INITIAL_SOUND_HINT.get(value, fallback or value or "啊")
    if kind == "final":
        return FINAL_SOUND_HINT.get(value, fallback or value or "啊")
    return fallback or value


def ensure_tone_audio(num: str) -> Path | None:
    if num not in TONE:
        return None
    TONE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = TONE_AUDIO_DIR / f"tone_{num}.wav"
    if path.exists() and path.stat().st_size > 1000:
        return path
    sample_rate = 22050
    duration = 0.62
    start_level, end_level = TONE[num]["levels"]
    level_freq = {1: 185.0, 2: 220.0, 3: 262.0, 4: 330.0, 5: 392.0}
    f1 = level_freq.get(start_level, 262.0)
    f2 = level_freq.get(end_level, f1)
    frames = int(sample_rate * duration)
    phase = 0.0
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(frames):
            t = i / max(1, frames - 1)
            freq = f1 + (f2 - f1) * t
            phase += 2 * math.pi * freq / sample_rate
            # 轻微淡入淡出，听起来像一条声调线。
            fade = min(1.0, i / (sample_rate * 0.05), (frames - i) / (sample_rate * 0.08))
            amp = int(13500 * max(0.0, fade) * math.sin(phase))
            wf.writeframes(struct.pack("<h", amp))
    return path


def two_line_display_from_tokens(tokens: list[dict[str, str]], *, max_units_one_line: int = 34) -> str:
    words = [t.get("word", "") for t in tokens if t.get("word", "")]
    text_value = "".join(words)
    if compact_text_len(text_value) <= max_units_one_line or len(words) <= 1:
        return text_value
    total = sum(compact_text_len(w) for w in words)
    target = total / 2
    best_i, best_diff, acc = 1, float("inf"), 0
    for i, word in enumerate(words[:-1], 1):
        acc += compact_text_len(word)
        diff = abs(acc - target)
        if diff < best_diff:
            best_i, best_diff = i, diff
    return "".join(words[:best_i]) + "\n" + "".join(words[best_i:])


def detect_cantonese_voice() -> str:
    try:
        proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=2)
        voices = proc.stdout or ""
    except Exception:
        return ""
    for name in ("Sin-ji", "Mei-Jia", "Ting-Ting"):
        if name in voices:
            return name
    return ""


CANTONESE_VOICE = detect_cantonese_voice()


# 分类例句库：给初学者直接点选练习，覆盖常见使用场景。
CATEGORY_EXAMPLES = {
    "常用": ["你好", "谢谢你", "不好意思", "你在哪里", "现在多少钱", "我想吃饭", "我不会粤语", "请再说一次", "慢一点说", "我想去学校图书馆"],
    "吃饭": ["你吃饭了吗", "我饿了", "我渴了", "我想喝水", "我想喝奶茶", "我要点餐", "我要买单", "可以打包吗", "不要辣", "少冰", "等位多久", "有菜单吗"],
    "出行": ["我要坐地铁", "我要坐公交车", "我要打车", "公交车站在哪里", "地铁站在哪里", "怎么走", "左转", "右转", "直走", "到了吗", "我迷路了", "我要去机场"],
    "购物": ["我要买东西", "我要买衣服", "这个多少钱", "这个太贵了", "可以便宜点吗", "我想试一下", "可以刷卡吗", "可以扫码吗", "有发票吗", "我要退货"],
    "看病": ["我要看医生", "我去看医生", "我不舒服", "我头痛", "我发烧", "我咳嗽", "我肚子痛", "我牙痛", "医院在哪里", "药店在哪里", "打急救电话"],
    "酒店": ["我要入住", "我要退房", "我订了房间", "有没有房间", "房间多少钱", "我要换房", "空调坏了", "没有热水", "可以开发票吗"],
    "学校": ["我要上学", "我要上课", "我下课了", "我要做作业", "我要考试", "我想看书", "我想读书", "我不会写", "我听不懂", "请再说一次", "慢一点说"],
    "工作": ["我要上班", "我要下班", "我要开会", "我要加班", "我要请假", "我今天很忙", "我在工作", "我迟到了", "我马上到", "我马上回来", "等一下"],
    "手机": ["我要打电话", "我要发消息", "我要发微信", "我手机没电", "我要充电", "有没有wifi", "网络不好", "我上不了网", "密码是什么", "我找不到", "已经好了"],
    "娱乐": ["我们去看电影吧", "我想看电影", "我想看电视", "我想听歌", "我想拍照", "帮我拍照", "可以拍照吗", "我想聊天", "我们一起去", "你等我一下"],
    "天气": ["今天几号", "现在几点", "明天几点", "今天很热", "今天很冷", "下雨了", "带伞", "我马上来"],
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("中文转粤语声调")
        try:
            self.tk.call("tk", "appname", "中文转粤语声调")
        except tk.TclError:
            pass
        self.geometry("1380x860")
        self.minsize(1120, 720)
        self.tokens: list[dict[str, str]] = []
        self.cantonese_text = ""
        self._resize_job = None
        self._history_save_job = None
        self._history_enabled = False
        self.history_records = load_history()
        self.history_filter = "recent"
        self.teach_mode = tk.BooleanVar(value=True)
        self.selected_index: int | None = None
        self.example_category = "常用"
        self.example_page = 0
        self.speech_proc = None

        self.bg = "#f4f8fb"
        self.sidebar_bg = "#14242b"
        self.panel = "#ffffff"
        self.card = "#ffffff"
        self.card_selected = "#e7f8fb"
        self.line = "#d7e6ea"
        self.accent = "#087c92"
        self.accent_dark = "#045a6b"
        self.muted = "#65757e"
        self.warn = "#b56b18"
        self.configure(bg=self.bg)

        style = ttk.Style(self)
        # 保留 macOS 原生控件，同时用自己的卡片/侧栏做现代布局。
        style.configure("TFrame", background=self.bg)
        style.configure("Panel.TFrame", background=self.panel)
        style.configure("TLabel", background=self.bg, foreground="#1f2a30")
        style.configure("Panel.TLabel", background=self.panel, foreground="#1f2a30")
        style.configure("Muted.TLabel", background=self.bg, foreground=self.muted)
        style.configure("PanelMuted.TLabel", background=self.panel, foreground=self.muted)
        style.configure("TCheckbutton", background=self.panel)

        root = tk.Frame(self, bg=self.bg)
        root.pack(fill="both", expand=True)

        sidebar = tk.Frame(root, bg=self.sidebar_bg, width=166)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="粤语\nTone", bg=self.sidebar_bg, fg="#ffffff", justify="left", font=("TkDefaultFont", 22, "bold")).pack(anchor="w", padx=18, pady=(22, 4))
        tk.Label(sidebar, text="离线学习工具", bg=self.sidebar_bg, fg="#8fb8c3", font=("TkDefaultFont", 11)).pack(anchor="w", padx=18, pady=(0, 18))
        self.make_nav_button(sidebar, "翻译", lambda: self.entry.focus_set(), active=True).pack(fill="x", padx=12, pady=(0, 8))
        self.make_nav_button(sidebar, "拆音学习", self.open_split_learning).pack(fill="x", padx=12, pady=(0, 8))
        self.make_nav_button(sidebar, "声调总表", self.show_general_lesson).pack(fill="x", padx=12, pady=(0, 8))
        self.make_nav_button(sidebar, "输入记录", lambda: self.set_history_filter("recent")).pack(fill="x", padx=12, pady=(0, 8))
        self.make_nav_button(sidebar, "补充词库", self.add_word).pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(sidebar, text=f"词库\n{ENTRY_COUNT:,} 条", bg=self.sidebar_bg, fg="#8fb8c3", justify="left", font=("TkDefaultFont", 11)).pack(side="bottom", anchor="w", padx=18, pady=(0, 18))

        body = tk.Frame(root, bg=self.bg, padx=18, pady=16)
        body.pack(side="left", fill="both", expand=True)

        hero = tk.Frame(body, bg=self.bg)
        hero.pack(fill="x")
        hero_left = tk.Frame(hero, bg=self.bg)
        hero_left.pack(side="left", fill="x", expand=True)
        tk.Label(hero_left, text="中文转粤语声调", bg=self.bg, fg="#1e2a30", font=("TkDefaultFont", 26, "bold")).pack(anchor="w")
        tk.Label(
            hero_left,
            text="输入普通中文，自动转日常粤语；词卡显示声调线、粤拼、译音和拆音；可离线朗读。",
            bg=self.bg,
            fg=self.muted,
            font=("TkDefaultFont", 12),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        badge_row = tk.Frame(hero_left, bg=self.bg)
        badge_row.pack(anchor="w", pady=(10, 0))
        for label in ["离线", "两行词卡", "拆音学习", "粤语朗读"]:
            tk.Label(badge_row, text=label, bg="#e7f8fb", fg=self.accent_dark, padx=10, pady=3, font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=(0, 6))

        input_card = tk.Frame(body, bg=self.panel, highlightbackground=self.line, highlightthickness=1, padx=14, pady=12)
        input_card.pack(fill="x", pady=(14, 10))
        tk.Label(input_card, text="输入中文", bg=self.panel, fg=self.muted, font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        search = tk.Frame(input_card, bg=self.panel)
        search.pack(fill="x", pady=(7, 0))
        self.input_var = tk.StringVar(value="我想去学校图书馆")
        self.entry = ttk.Entry(search, textvariable=self.input_var, font=("TkDefaultFont", 22))
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.make_action_button(search, "转换", self.render, primary=True).pack(side="left", padx=(10, 0))
        self.make_action_button(search, "朗读", self.speak_cantonese).pack(side="left", padx=(8, 0))
        self.make_action_button(search, "拆音", self.open_split_learning).pack(side="left", padx=(8, 0))
        action_row = tk.Frame(input_card, bg=self.panel)
        action_row.pack(fill="x", pady=(8, 0))
        self.make_action_button(action_row, "复制粤语", self.copy_cantonese).pack(side="left")
        self.make_action_button(action_row, "复制全部", self.copy_all).pack(side="left", padx=(8, 0))
        self.make_action_button(action_row, "补充词", self.add_word).pack(side="left", padx=(8, 0))

        result_card = tk.Frame(body, bg=self.panel, highlightbackground=self.line, highlightthickness=1, padx=14, pady=10)
        result_card.pack(fill="x", pady=(0, 10))
        result_frame = tk.Frame(result_card, bg=self.panel)
        result_frame.pack(fill="x")
        tk.Label(result_frame, text="粤语", bg=self.panel, fg=self.muted, font=("TkDefaultFont", 11, "bold")).pack(side="left", padx=(0, 10))
        self.canto_var = tk.StringVar(value="")
        self.canto_label = tk.Label(result_frame, textvariable=self.canto_var, bg=self.panel, fg="#1d2a30", font=("TkDefaultFont", 18, "bold"), wraplength=1050, justify="left", anchor="w")
        self.canto_label.pack(side="left", fill="x", expand=True)
        self.sound_hint_var = tk.StringVar(value="")
        tk.Label(result_card, textvariable=self.sound_hint_var, bg=self.panel, fg=self.muted, font=("TkDefaultFont", 12), wraplength=1160, justify="left").pack(anchor="w", pady=(6, 0), fill="x")

        quick_grid = tk.Frame(body, bg=self.bg)
        quick_grid.pack(fill="x", pady=(0, 10))
        examples_panel = tk.Frame(quick_grid, bg=self.panel, highlightbackground=self.line, highlightthickness=1, padx=12, pady=9)
        examples_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        category_row = tk.Frame(examples_panel, bg=self.panel)
        category_row.pack(fill="x")
        tk.Label(category_row, text="分类例句", bg=self.panel, fg=self.muted, font=("TkDefaultFont", 11, "bold")).pack(side="left", padx=(0, 8))
        self.category_buttons: dict[str, tk.Button] = {}
        self.category_var = tk.StringVar(value=self.example_category)
        self.category_combo = ttk.Combobox(category_row, textvariable=self.category_var, values=list(CATEGORY_EXAMPLES), state="readonly", width=8, font=("TkDefaultFont", 11))
        self.category_combo.pack(side="left", padx=(0, 8))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _event: self.set_example_category(self.category_var.get()))
        self.make_chip(category_row, "换一批", self.next_example_page).pack(side="left", padx=(0, 0), pady=(0, 2))
        self.example_count_var = tk.StringVar(value="")
        tk.Label(category_row, textvariable=self.example_count_var, bg=self.panel, fg=self.muted, font=("TkDefaultFont", 10)).pack(side="left", padx=(8, 0))
        self.example_items_frame = tk.Frame(examples_panel, bg=self.panel)
        self.example_items_frame.pack(fill="x", pady=(5, 0))

        history_panel = tk.Frame(quick_grid, bg=self.panel, highlightbackground=self.line, highlightthickness=1, padx=12, pady=9)
        history_panel.pack(side="right", fill="both", expand=True)
        top_history = tk.Frame(history_panel, bg=self.panel)
        top_history.pack(fill="x")
        tk.Label(top_history, text="输入记录", bg=self.panel, fg=self.muted, font=("TkDefaultFont", 11, "bold")).pack(side="left", padx=(0, 8))
        self.history_buttons: dict[str, tk.Button] = {}
        for key, label in [("recent", "最近"), ("week", "一周"), ("month", "一月"), ("year", "一年")]:
            btn = self.make_chip(top_history, label, lambda k=key: self.set_history_filter(k))
            btn.pack(side="left", padx=(0, 6))
            self.history_buttons[key] = btn
        self.history_count_var = tk.StringVar(value="")
        tk.Label(top_history, textvariable=self.history_count_var, bg=self.panel, fg=self.muted, font=("TkDefaultFont", 10)).pack(side="left", padx=(8, 0))
        self.history_items_frame = tk.Frame(history_panel, bg=self.panel)
        self.history_items_frame.pack(fill="x", pady=(5, 0))

        main = tk.Frame(body, bg=self.bg)
        main.pack(fill="both", expand=True)
        left = tk.Frame(main, bg=self.bg)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(main, bg=self.panel, highlightbackground=self.line, highlightthickness=1, padx=18, pady=18)
        right.pack(side="right", fill="y", padx=(16, 0))
        right.configure(width=390)
        right.pack_propagate(False)

        canvas_frame = tk.Frame(left, bg=self.panel, highlightbackground=self.line, highlightthickness=1, padx=10, pady=10)
        canvas_frame.pack(fill="both", expand=True)
        tk.Label(canvas_frame, text="两行词卡", bg=self.panel, fg=self.muted, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 6))
        self.canvas = tk.Canvas(canvas_frame, bg="#fbfcfc", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        # 结果区取消滚动条和鼠标滚动：只显示当前可见词卡，避免误以为下面漏了内容。
        self.canvas.bind("<Configure>", self.on_resize)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.status = tk.Label(left, text="", bg=self.bg, fg=self.warn, font=("TkDefaultFont", 11))
        self.status.pack(anchor="w", pady=(8, 0))
        self.output_var = tk.StringVar(value="")
        tk.Label(left, textvariable=self.output_var, wraplength=820, bg=self.bg, fg=self.muted, font=("TkDefaultFont", 10), justify="left").pack(anchor="w", pady=(4, 0), fill="x")

        tk.Label(right, text="固定教学", bg=self.panel, fg="#1e2a30", font=("TkDefaultFont", 20, "bold")).pack(anchor="w")
        ttk.Checkbutton(right, text="教学模式", variable=self.teach_mode, command=self.refresh_teaching_hint).pack(anchor="w", pady=(8, 6))
        teach_buttons = tk.Frame(right, bg=self.panel)
        teach_buttons.pack(anchor="w", pady=(0, 10), fill="x")
        self.make_action_button(teach_buttons, "声调总表", self.show_general_lesson).pack(side="left")
        self.make_action_button(teach_buttons, "拆音学习", self.open_split_learning).pack(side="left", padx=(8, 0))
        tk.Label(right, text="点左边任意词卡，这里会同步讲解。粤拼和中文译音后面的 ˉ ˊ ˋ ˇ ˍ 是声调形状；同一卡片直接连写，代表一组连读。", bg=self.panel, fg=self.muted, font=("TkDefaultFont", 11), wraplength=340, justify="left").pack(anchor="w", pady=(0, 8))
        self.lesson_text = tk.Text(
            right,
            wrap="word",
            height=24,
            bg=self.panel,
            fg="#20282c",
            relief="flat",
            borderwidth=0,
            padx=0,
            pady=0,
            font=("TkDefaultFont", 14),
        )
        self.lesson_text.pack(fill="both", expand=True)
        self.lesson_text.configure(state="disabled")

        self.input_var.trace_add("write", lambda *_: self.render())
        self.set_lesson("教学模式已开启。点左边词卡，可以边看词卡边看教程。\n\n" + general_tone_guide())
        self.render()
        self._history_enabled = True
        self.refresh_category_examples()
        self.refresh_history_view()

    def on_close(self) -> None:
        self.stop_speech()
        self.destroy()

    def make_action_button(self, parent, text: str, command, primary: bool = False) -> tk.Button:
        bg = self.accent if primary else "#e8eef0"
        # macOS Aqua often ignores custom button backgrounds, so keep text dark for contrast.
        fg = "#203238"
        active_bg = self.accent_dark if primary else "#dce7ea"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="pointinghand",
            font=("TkDefaultFont", 13, "bold"),
        )

    def make_nav_button(self, parent, text: str, command, active: bool = False) -> tk.Button:
        # macOS 对 tk.Button 背景支持有限，所以这里用高对比文字保证清楚。
        bg = "#ffffff" if active else "#e8eef0"
        fg = "#14242b" if active else "#203238"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground="#d9f2f7",
            activeforeground="#14242b",
            relief="flat",
            bd=0,
            padx=14,
            pady=10,
            anchor="w",
            cursor="pointinghand",
            font=("TkDefaultFont", 12, "bold"),
        )

    def make_chip(self, parent, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#ffffff",
            fg="#243036",
            activebackground="#e4f7fb",
            activeforeground="#075968",
            relief="solid",
            bd=1,
            padx=8,
            pady=3,
            cursor="pointinghand",
            font=("TkDefaultFont", 10),
        )

    def set_lesson(self, text: str) -> None:
        self.lesson_text.configure(state="normal")
        self.lesson_text.delete("1.0", "end")
        self.lesson_text.insert("1.0", text)
        self.lesson_text.configure(state="disabled")

    def set_example(self, text: str) -> None:
        self.input_var.set(text)
        self.entry.focus_set()
        self.entry.icursor("end")

    def set_example_category(self, key: str) -> None:
        if key not in CATEGORY_EXAMPLES:
            return
        self.example_category = key
        if hasattr(self, "category_var"):
            self.category_var.set(key)
        self.example_page = 0
        self.refresh_category_examples()

    def next_example_page(self) -> None:
        items = CATEGORY_EXAMPLES.get(self.example_category, [])
        if not items:
            return
        page_size = 4
        pages = max(1, (len(items) + page_size - 1) // page_size)
        self.example_page = (self.example_page + 1) % pages
        self.refresh_category_examples()

    def refresh_category_examples(self) -> None:
        if not hasattr(self, "example_items_frame"):
            return
        for child in self.example_items_frame.winfo_children():
            child.destroy()
        if hasattr(self, "category_var"):
            self.category_var.set(self.example_category)
        for key, btn in getattr(self, "category_buttons", {}).items():
            if key == self.example_category:
                btn.configure(bg="#dff6fa", fg=self.accent_dark)
            else:
                btn.configure(bg="#ffffff", fg="#243036")
        items = CATEGORY_EXAMPLES.get(self.example_category, [])
        page_size = 4
        if not items:
            self.example_count_var.set("")
            return
        pages = max(1, (len(items) + page_size - 1) // page_size)
        self.example_page %= pages
        start = self.example_page * page_size
        visible = items[start:start + page_size]
        end = start + len(visible)
        self.example_count_var.set(f"{start + 1}-{end}/{len(items)}")
        for text in visible:
            self.make_chip(self.example_items_frame, text, lambda t=text: self.set_example(t)).pack(side="left", padx=(0, 6), pady=(0, 2))

    def set_history_filter(self, key: str) -> None:
        self.history_filter = key
        self.refresh_history_view()

    def history_cutoff(self) -> int | None:
        now = int(time.time())
        if self.history_filter == "week":
            return now - 7 * 86400
        if self.history_filter == "month":
            return now - 30 * 86400
        if self.history_filter == "year":
            return now - 365 * 86400
        return None

    def history_visible_records(self) -> list[dict[str, object]]:
        cutoff = self.history_cutoff()
        query = self.input_var.get().strip()
        records = []
        for item in self.history_records:
            ts = int(item.get("ts", 0) or 0)
            if cutoff is not None and ts < cutoff:
                continue
            text_value = str(item.get("text", ""))
            cantonese = str(item.get("cantonese", ""))
            if query and query not in text_value and query not in cantonese:
                continue
            records.append(item)
        if query and len(records) < 8:
            # 输入时也补显示最近记录，避免列表突然空掉。
            for item in self.history_records:
                if item in records:
                    continue
                ts = int(item.get("ts", 0) or 0)
                if cutoff is not None and ts < cutoff:
                    continue
                records.append(item)
                if len(records) >= 3:
                    break
        return records[:3]

    def refresh_history_view(self) -> None:
        if not hasattr(self, "history_items_frame"):
            return
        for child in self.history_items_frame.winfo_children():
            child.destroy()
        for key, btn in getattr(self, "history_buttons", {}).items():
            if key == self.history_filter:
                btn.configure(bg="#dff6fa", fg=self.accent_dark)
            else:
                btn.configure(bg="#ffffff", fg="#243036")
        visible = self.history_visible_records()
        total = len(self.history_records)
        names = {"recent": "最近", "week": "一周", "month": "一月", "year": "一年"}
        self.history_count_var.set(f"{names.get(self.history_filter, '最近')} {len(visible)} / 总 {total}")
        if not visible:
            ttk.Label(self.history_items_frame, text="暂无记录，输入后会自动保存。", style="Muted.TLabel").pack(side="left")
            return
        for item in visible:
            text_value = str(item.get("text", ""))
            ts = int(item.get("ts", 0) or 0)
            label = text_value if len(text_value) <= 6 else text_value[:6] + "…"
            tlabel = history_time_label(ts)
            btn_text = f"{label} · {tlabel}" if tlabel else label
            self.make_chip(self.history_items_frame, btn_text, lambda t=text_value: self.use_history(t)).pack(side="left", padx=(0, 6), pady=(0, 2))

    def use_history(self, text: str) -> None:
        self.input_var.set(text)
        self.entry.focus_set()
        self.entry.icursor("end")

    def schedule_history_record(self) -> None:
        if not self._history_enabled:
            return
        if self._history_save_job:
            self.after_cancel(self._history_save_job)
        self._history_save_job = self.after(900, self.commit_history_record)

    def commit_history_record(self) -> None:
        self._history_save_job = None
        text_value = self.input_var.get().strip()
        if not text_value:
            return
        self.history_records = add_history_record(self.history_records, text_value, self.cantonese_text)
        save_history(self.history_records)
        self.refresh_history_view()

    def copy_cantonese(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.cantonese_text)
        self.status.configure(text="已复制粤语。")

    def copy_all(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(f"粤语：{self.cantonese_text}\n音标：{self.output_var.get()}")
        self.status.configure(text="已复制全部。")

    def stop_speech(self) -> None:
        proc = getattr(self, "speech_proc", None)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self.speech_proc = None

    def say_text(self, text_value: str, label: str = "朗读") -> None:
        text_value = str(text_value or "").strip()
        if not text_value:
            self.status.configure(text="没有可读内容。")
            return
        self.stop_speech()
        try:
            cmd = ["say"]
            if CANTONESE_VOICE:
                cmd += ["-v", CANTONESE_VOICE]
            cmd += [text_value]
            self.speech_proc = subprocess.Popen(cmd)
            voice_name = CANTONESE_VOICE or "系统默认"
            self.status.configure(text=f"{label}：{text_value}（{voice_name}）。")
        except Exception as exc:
            self.status.configure(text=f"朗读启动出错：{exc}")

    def speak_cantonese(self) -> None:
        self.say_text(self.cantonese_text, "整句朗读")

    def speak_component(self, kind: str, value: str, fallback: str = "") -> None:
        spoken = component_voice_text(kind, value, fallback)
        label = "声母" if kind == "initial" else "韵母"
        self.say_text(spoken, f"{label} {value or '零声母'}")

    def play_tone_shape(self, num: str) -> None:
        path = ensure_tone_audio(num)
        if not path:
            return
        self.stop_speech()
        self.speech_proc = subprocess.Popen(["afplay", str(path)])
        self.status.configure(text=f"声调：{tone_part_label(num)} {TONE[num]['name']}")

    def refresh_teaching_hint(self) -> None:
        if self.teach_mode.get():
            self.set_lesson("教学模式已开启。点左边词卡，可以边看词卡边看教程。\n\n" + general_tone_guide())
        else:
            self.set_lesson("教学模式已关闭。左边仍显示声调线、粤拼和中文近似音译。")

    def show_general_lesson(self) -> None:
        self.set_lesson(general_tone_guide())

    def show_token_lesson(self, token: dict[str, str], index: int | None = None) -> None:
        if index is not None:
            self.selected_index = index
            self.draw_tokens()
        if not self.teach_mode.get():
            return
        word = token.get("word", "")
        jp = token.get("jp", "")
        syllables = split_jp(jp)
        if not syllables:
            self.set_lesson(f"{word}：这个不是粤语音节，可能是标点、英文或未收录内容。")
            return
        join_tip = "这一张卡是一组连读：读的时候一口气读完，但每个字的声调仍然保留。" if len(syllables) > 1 else "这是单音节；和下一张卡连起来读时，中间不要拖太长。"
        parts = [f"{word}\n\n粤拼：{jyutping_with_marks(jp)}\n拆音：{split_sound_line_for_jp(jp)}\n中文译音连读：{chinese_sound_for_token(word, jp, joiner='')}\n逐音节：{chinese_sound_for_jp(jp, with_tone_name=True, joiner=' / ')}\n连读：{join_tip}\n\n点“拆音学习”可以分别听：文字、声母、韵母、声调线。"]
        parts.append("—" * 18)
        parts.extend(explain_syllable(base, num) for base, num in syllables)
        self.set_lesson("\n\n".join(parts))

    def syllable_units(self) -> list[dict[str, str]]:
        units: list[dict[str, str]] = []
        for token in self.tokens:
            word = token.get("word", "")
            jp = token.get("jp", "")
            syllables = split_jp(jp)
            if not syllables:
                continue
            chars = list(word)
            char_aligned = len(chars) == len(syllables)
            for idx, (base, num) in enumerate(syllables):
                initial, final = split_initial_final(base)
                char = chars[idx] if char_aligned else (word if len(syllables) == 1 else "")
                units.append({
                    "word": word,
                    "char": char,
                    "base": base,
                    "num": num,
                    "initial": initial,
                    "final": final,
                    "marked": jyutping_with_marks(f"{base}{num}"),
                    "split": split_sound_text(base, num),
                    "sound": chinese_sound_for_jp(f"{base}{num}", joiner=""),
                })
        return units

    def open_split_learning(self) -> None:
        units = self.syllable_units()
        win = tk.Toplevel(self)
        win.title("拆音学习")
        win.geometry("760x640")
        win.minsize(620, 460)
        win.configure(bg=self.bg)
        root = ttk.Frame(win, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="拆音学习", font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="每个粤拼拆成：声母 + 韵母 + 声调形状。文字、声母、韵母、声调都可以单独听；非常规读法也按这个规则自定义学习。",
            style="Muted.TLabel",
            wraplength=700,
        ).pack(anchor="w", pady=(4, 10))

        top_actions = ttk.Frame(root)
        top_actions.pack(fill="x", pady=(0, 10))
        self.make_action_button(top_actions, "读整句", self.speak_cantonese).pack(side="left")
        self.make_action_button(top_actions, "读粤语文字", lambda: self.say_text(self.cantonese_text, "粤语文字")).pack(side="left", padx=(8, 0))

        tone_box = ttk.Frame(root)
        tone_box.pack(fill="x", pady=(0, 10))
        ttk.Label(tone_box, text="六个声调：", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        for num in ["1", "2", "3", "4", "5", "6"]:
            label = f"{tone_part_label(num)} {TONE[num]['name']}"
            self.make_chip(tone_box, label, lambda n=num: self.play_tone_shape(n)).pack(side="left", padx=(0, 6), pady=(0, 3))

        canvas = tk.Canvas(root, bg="#fbfcfc", highlightthickness=1, highlightbackground=self.line)
        scroll = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        if not units:
            ttk.Label(inner, text="先输入一句中文，再打开这里练习拆音。", style="Muted.TLabel").pack(anchor="w", padx=12, pady=12)
            return

        for unit in units:
            row = ttk.Frame(inner, padding=(10, 8))
            row.pack(fill="x", padx=8, pady=(8, 0))
            title = unit["char"] or unit["word"] or unit["base"]
            ttk.Label(row, text=f"{title}  {unit['marked']}", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
            ttk.Label(row, text=f"拆音：{unit['split']}    译音：{unit['sound']}", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
            btns = ttk.Frame(row)
            btns.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))
            row.columnconfigure(0, weight=1)
            self.make_chip(btns, "读字", lambda u=unit: self.say_text(u['char'] or u['word'], "文字")).pack(side="left", padx=(0, 4))
            self.make_chip(btns, "读词", lambda u=unit: self.say_text(u['word'], "词组")).pack(side="left", padx=(0, 4))
            self.make_chip(btns, "声母", lambda u=unit: self.speak_component("initial", u['initial'], u['char'] or u['word'])).pack(side="left", padx=(0, 4))
            self.make_chip(btns, "韵母", lambda u=unit: self.speak_component("final", u['final'], u['char'] or u['word'])).pack(side="left", padx=(0, 4))
            self.make_chip(btns, "声调", lambda u=unit: self.play_tone_shape(u['num'])).pack(side="left")

    def add_word(self) -> None:
        word = simpledialog.askstring("补充词", "输入粤语词：", parent=self)
        if not word:
            return
        jp = simpledialog.askstring("补充词", "输入粤拼，例如：san1 ci4", parent=self)
        if not jp:
            return
        jp = jp.strip().lower()
        if not all(JP_RE.match(item) for item in jp.split()):
            messagebox.showerror("格式不对", "粤拼要带 1-6 声调数字，例如：nei5 hou2")
            return
        LEXICON[word.strip()] = jp
        append_user_lexicon(word.strip(), jp)
        self.status.configure(text=f"已补充：{word.strip()} = {jp}")
        self.render()

    def open_user_lexicon_path(self) -> None:
        self.status.configure(text=f"补充词库位置：{USER_LEXICON_PATH}")

    def on_resize(self, _event=None) -> None:
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self.draw_tokens)

    def render(self) -> None:
        self.cantonese_text = translate_to_cantonese(self.input_var.get())
        self.tokens = segment(self.cantonese_text)
        display_text = two_line_display_from_tokens(self.tokens)
        self.canto_var.set(display_text)
        if hasattr(self, "canto_label"):
            self.canto_label.configure(font=("TkDefaultFont", auto_font_size(self.cantonese_text, base=15, min_size=10, ideal=42, step_chars=10)))
        self.selected_index = None
        unknown = [t["word"] for t in self.tokens if t["kind"] == "unknown"]
        self.status.configure(text=("未收录：" + "、".join(unknown[:20])) if unknown else "")
        self.output_var.set(linear(self.tokens))
        self.sound_hint_var.set("中文译音连读：" + sound_line(self.tokens) + "    （同一组直接连写；/ 表示可小停顿；ˉˊˋˇˍ 表示声调形状）")
        self.refresh_history_view()
        self.schedule_history_record()
        self.draw_tokens()

    def draw_tokens(self) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width() - 4, 660)
        x, y0 = 18, 14
        visible_h = max(self.canvas.winfo_height() - 12, 240)
        gap = 12
        max_rows = 2
        hidden_count = 0
        dense = len(self.tokens) >= 5 or compact_text_len(self.cantonese_text) > 18
        # 默认一句短话用更高卡片；长句需要两行时再自动压缩。
        estimated_width = 18
        estimated_rows = 1
        for token in self.tokens:
            sylls0 = split_jp(token.get("jp", ""))
            n0 = max(len(sylls0), len(token.get("word", "")), 1)
            cw0 = max(112, min(250, 36 * n0 + 56)) if dense else max(132, min(290, 44 * n0 + 60))
            if estimated_width + cw0 > width - 18:
                estimated_rows += 1
                estimated_width = 18 + cw0 + gap
            else:
                estimated_width += cw0 + gap
        if estimated_rows <= 1:
            row_h = min(204, max(170, visible_h - 34))
        else:
            row_h = min(178, max(128, int((visible_h - 30 - gap) / 2)))
        for index, token in enumerate(self.tokens):
            jp = token["jp"]
            sylls = split_jp(jp)
            n = max(len(sylls), len(token["word"]), 1)
            # 字多时卡片变紧凑，但给多音节连读组保留足够宽度，避免字和粤拼挤在一起。
            if dense:
                card_w = max(112, min(250, 36 * n + 56))
            else:
                card_w = max(132, min(290, 44 * n + 60))
            if token["kind"] in {"punct", "plain"}:
                card_w = max(58, min(112, 22 * len(token["word"]) + 28))
            if x + card_w > width - 18:
                x = 18
                y0 += row_h + gap
            current_row = int((y0 - 14) / (row_h + gap))
            if current_row >= max_rows:
                hidden_count += 1
                continue
            self.draw_card(x, y0, card_w, row_h, token, sylls, index)
            x += card_w + gap
        # 取消滚动区域，让画布固定为两行显示。
        self.canvas.configure(scrollregion=(0, 0, width, visible_h))
        if hidden_count:
            self.canvas.create_text(
                width - 24, max(24, visible_h - 18),
                text=f"内容较长，先显示两行，余下 {hidden_count} 张；可拆短句查看。",
                anchor="se", fill=self.warn, font=("TkDefaultFont", 10, "bold")
            )

    def draw_card(self, x: int, y: int, w: int, h: int, token: dict[str, str], sylls: list[tuple[str, str]], index: int) -> None:
        known = token["kind"] == "known"
        selected = index == self.selected_index
        fill = self.card_selected if selected else (self.card if known else ("#f7f7f7" if token["kind"] != "unknown" else "#fff7ec"))
        outline = self.accent if selected else (self.line if known else ("#eeeeee" if token["kind"] != "unknown" else "#d99a48"))
        tag = f"card_{index}"
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill, outline=outline, width=2 if selected else 1, tags=(tag,))
        self.canvas.create_rectangle(x + 6, y + 6, x + w - 6, y + h - 6, fill=fill, outline="", tags=(tag,))
        compact_card = h < 158 or w < 150
        multi = len(sylls) > 1
        long_group = len(sylls) >= 3 or compact_text_len(token.get("word", "")) >= 3
        badge = "连读组" if multi else "单字"
        badge_font = 9 if compact_card else 10
        self.canvas.create_text(x + w - 13, y + 17, text=badge, anchor="ne", font=("TkDefaultFont", badge_font, "bold"), fill=self.muted, tags=(tag,))
        tone_h = 28 if compact_card else 32
        self.draw_tones(x + 14, y + 24, w - 28, tone_h, sylls)
        raw_jp = token["jp"] if token["jp"] else ""
        jp_text = jyutping_with_marks(raw_jp) if raw_jp else ""
        sound_text = chinese_sound_for_token(token.get("word", ""), raw_jp, joiner="") if raw_jp else ""

        word_base = 19 if compact_card else 23
        word_min = 12 if compact_card else 14
        jp_base = 11 if compact_card else 13
        jp_min = 9 if compact_card else 10
        sound_base = 11 if compact_card else 12
        word_font = auto_font_size(token.get("word", ""), base=word_base, min_size=word_min, ideal=5 if compact_card else 6, step_chars=2)
        jp_font = auto_font_size(jp_text, base=jp_base, min_size=jp_min, ideal=16 if compact_card else 22, step_chars=6)
        sound_font = auto_font_size(sound_text, base=sound_base, min_size=9, ideal=15 if compact_card else 18, step_chars=6)
        if compact_card and long_group:
            word_font = min(word_font, 17)
            jp_font = min(jp_font, 10)
            sound_font = min(sound_font, 10)

        word_y = y + int(h * (0.37 if compact_card else 0.41))
        jp_y = y + int(h * (0.53 if compact_card else 0.55))
        sound_top = y + int(h * (0.60 if compact_card else 0.62))
        sound_bottom = y + int(h * (0.76 if compact_card else 0.77))
        sound_y = (sound_top + sound_bottom) / 2
        # 拆音行是学习重点，不能贴底；往上放，避免被画布底边裁掉。
        name_y = y + int(h * (0.86 if compact_card else 0.87))
        self.canvas.create_text(x + w / 2, word_y, text=token["word"], font=("TkDefaultFont", word_font, "bold"), fill="#111111", width=max(70, w - 18), tags=(tag,))
        self.canvas.create_text(x + w / 2, jp_y, text=jp_text, font=("TkDefaultFont", jp_font, "bold"), fill="#233036", width=max(70, w - 20), tags=(tag,))
        self.canvas.create_rectangle(x + 10, sound_top, x + w - 10, sound_bottom, fill="#e7f7fa", outline="#d2edf2", tags=(tag,))
        self.canvas.create_text(x + w / 2, sound_y, text="译音：" + sound_text if sound_text else "", font=("TkDefaultFont", sound_font, "bold"), fill=self.accent_dark, width=max(70, w - 26), tags=(tag,))
        split_label = "拆：" + card_split_sound_line(raw_jp) if raw_jp else ""
        name_font = auto_font_size(split_label, base=9 if compact_card else 10, min_size=8, ideal=30 if compact_card else 38, step_chars=10)
        self.canvas.create_text(x + w / 2, name_y, text=split_label, font=("TkDefaultFont", name_font, "bold"), fill=self.muted, width=max(86, w - 16), tags=(tag,))
        self.canvas.tag_bind(tag, "<Button-1>", lambda _event, idx=index: self.show_token_lesson(self.tokens[idx], idx))

    def draw_tones(self, x: int, y: int, w: int, h: int, sylls: list[tuple[str, str]]) -> None:
        if not sylls:
            self.canvas.create_line(x + 6, y + h / 2, x + w - 6, y + h / 2, fill="#dddddd", width=2)
            return
        count = len(sylls)
        seg_w = w / count
        for idx, (_base, num) in enumerate(sylls):
            sx = x + idx * seg_w
            self.canvas.create_line(sx + 4, y + 8, sx + seg_w - 4, y + 8, fill="#e4ecef")
            self.canvas.create_line(sx + 4, y + h / 2, sx + seg_w - 4, y + h / 2, fill="#e9eef0")
            self.canvas.create_line(sx + 4, y + h - 8, sx + seg_w - 4, y + h - 8, fill="#e4ecef")
            if num not in TONE:
                self.canvas.create_text(sx + seg_w / 2, y + h / 2, text="?", fill="#b24818", font=("TkDefaultFont", 16, "bold"))
                continue
            a, b = TONE[num]["levels"]
            px1 = sx + 10
            px2 = sx + seg_w - 10
            py1 = y + 6 + (5 - a) * ((h - 12) / 4)
            py2 = y + 6 + (5 - b) * ((h - 12) / 4)
            self.canvas.create_line(px1, py1, px2, py2, fill=self.accent, width=4, capstyle="round")
            self.canvas.create_oval(px1 - 3, py1 - 3, px1 + 3, py1 + 3, fill=self.accent, outline="")
            self.canvas.create_oval(px2 - 3, py2 - 3, px2 + 3, py2 + 3, fill=self.accent, outline="")

def self_test() -> None:
    cases = {
        "我想吃饭": ["我想食飯", "ngo5", "soeng2", "sik6", "faan6"],
        "你在哪里": ["你喺邊度", "nei5", "hai2", "bin1 dou6"],
        "现在多少钱": ["而家幾多錢", "ji4 gaa1", "gei2 do1 cin2"],
        "我们今天回家": ["我哋今日返屋企", "ngo5 dei6", "gam1 jat6", "faan1 uk1 kei5"],
        "这个多少钱": ["呢個幾多錢", "ni1 go3", "gei2 do1 cin2"],
        "公交车在哪里": ["巴士喺邊度", "baa1 si6", "hai2", "bin1 dou6"],
        "我想去学校图书馆": ["我想去學校圖書館", "ngo5", "soeng2", "heoi3", "hok6 haau6", "tou4 syu1 gun2"],
        "我想吃鸡腿": ["我想食雞腿", "gai1 teoi2"],
        "今晚几点睡觉": ["今晚幾點瞓覺", "gam1 maan5 gei2 dim2 fan3 gaau3"],
        "我睡不着": ["我瞓唔著", "fan3 m4 zoek6"],
        "我们去看电影吧": ["我哋去睇戲啦", "heoi3 tai2 hei3"],
        "我想看电视": ["我想睇電視", "tai2 din6 si6"],
        "我们去逛街": ["我哋去行街", "haang4 gaai1"],
        "我要坐地铁": ["我要搭地鐵", "daap3 dei6 tit3"],
        "我要上厕所": ["我要去廁所", "heoi3 ci3 so2"],
        "我想听歌": ["我想聽歌", "teng1 go1"],
        "我去看医生": ["我去睇醫生", "tai2 ji1 sang1"],
    }
    for source, expected in cases.items():
        canto = translate_to_cantonese(source)
        tokens = segment(canto)
        joined = " | ".join(t["jp"] for t in tokens if t["jp"])
        print(source, "=>", canto, "=>", joined)
        for item in expected:
            assert item in canto or item in joined
    assert split_initial_final("ngo") == ("ng", "o")
    assert "ng + o + ˇ" in explain_syllable("ngo", "5")
    assert "ˉ 高平" in general_tone_guide()
    assert "鹅" in chinese_sound_for_jp("ngo5")
    assert "图" in chinese_sound_for_jp("tou4 syu1 gun2")
    assert jyutping_with_marks("ngo5 soeng2 heoi3") == "ngoˇ soengˊ heoi"
    assert split_sound_line_for_jp("tai2 hon3") == "t + ai + ˊ / h + on + 中平"
    assert not re.search(r"[1-6]", split_sound_line_for_jp("tai2 hon3"))
    assert chinese_sound_for_jp("gai1 teoi2", joiner="") == "该ˉ推ˊ"
    assert chinese_sound_for_jp("fan3 gaau3", joiner="") == "芬交"
    assert chinese_sound_for_jp("maa3", joiner="") == "妈"
    assert_no_double_chinese_sound("maa3 teoi2 fan3 gaau3 heoi3 zoek6 jing2 hei3")
    assert chinese_sound_for_jp("din6 jing2", joiner="") == "电ˍ英ˊ"
    assert chinese_sound_for_token("睇戲", "tai2 hei3", joiner="") == "睇ˊ戏"
    assert chinese_sound_for_token("起身", "hei2 san1", joiner="") == "起ˊ身ˉ"
    assert chinese_sound_for_jp("tai2 hei3", joiner="") == "睇ˊ希"
    assert len(CJK_GLOBAL_RE.findall(chinese_sound_for_base("maa"))) <= 1
    assert_phrase_sound_shapes()
    hist = add_history_record([], "今晚几点睡觉", "今晚幾點瞓覺")
    assert hist and hist[0]["text"] == "今晚几点睡觉"
    assert any(t["word"] == "雞腿" and t["jp"] == "gai1 teoi2" for t in segment(translate_to_cantonese("鸡腿")))
    assert any(t["word"] == "我瞓唔著" and t["jp"] == "ngo5 fan3 m4 zoek6" for t in segment(translate_to_cantonese("我睡不着")))
    assert any(t["word"] == "今晚幾點瞓覺" and t["jp"] == "gam1 maan5 gei2 dim2 fan3 gaau3" for t in segment(translate_to_cantonese("今晚几点睡觉")))
    for sample in ["看电视", "听歌", "逛街", "坐地铁", "上厕所", "洗澡", "拍照", "看医生", "去看医生", "上课", "下课", "买东西", "点餐", "吃东西", "喝东西", "聊天", "看书", "做饭", "洗衣服", "充电", "手机没电", "找不到", "不舒服", "头痛", "发烧", "地铁站", "公交站", "看电影", "起床", "看新闻", "读书", "买衣服"]:
        canto = translate_to_cantonese(sample)
        tokens = segment(canto)
        assert tokens, sample
        for token in tokens:
            if token.get("jp") and token.get("jp") != "?":
                assert_no_double_chinese_sound(token["jp"])
    batch_samples = [
        "拜拜", "没事", "没问题", "你吃饭了吗", "我吃饱了", "我渴了", "可以打包吗", "少放辣", "不要冰", "等位多久",
        "可以刷卡吗", "有发票吗", "我想试一下", "我迷路了", "我起床了", "我不会写", "我听不懂", "请再说一次", "慢一点说",
        "我迟到了", "我肚子痛", "打急救电话", "我订了房间", "空调坏了", "有没有wifi", "密码是什么", "我上不了网",
        "已经好了", "今天很冷", "下雨了", "带伞", "我会一点粤语", "我不会粤语",
    ]
    for sample in batch_samples:
        canto = translate_to_cantonese(sample)
        tokens = segment(canto)
        assert not any(t.get("jp") == "?" for t in tokens), (sample, canto, tokens)
        assert not re.search(r"[a-z]{2,}", sound_line(tokens)), (sample, canto, sound_line(tokens))
    for group, examples in CATEGORY_EXAMPLES.items():
        assert examples, group
        for sample in examples:
            canto = translate_to_cantonese(sample)
            tokens = segment(canto)
            assert not any(t.get("jp") == "?" for t in tokens), (group, sample, canto, tokens)
            assert not re.search(r"[a-z]{2,}", sound_line(tokens)), (group, sample, canto, sound_line(tokens))
    print("self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        App().mainloop()
