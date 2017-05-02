# coding=utf-8
#
# CC-CEDICT 渲染工具
# by David Wang
# v2.0
# 2016-05-02 22:19
#
# 主要功能：下载CC-CEDICT数据文件，解压，解析数据文件并渲染成符合MDICT(HTML)格式的文件
#
# 相关链接：
#   download page of CC-CEDICT: http://www.mdbg.net/chindict/chindict.php?page=cc-cedict
#   CC-CEDICT file format: http://cc-cedict.org/wiki/format:syntax
#   Online page for word query: http://www.mdbg.net/chindict/chindict.php
#   Ajax to query details: http://www.mdbg.net/chindict/chindict_ajax.php?c=cdqchi&i=[word]
#   Ajax to query pronunction: http://www.mdbg.net/chindict/chindict_ajax.php?c=mpp&i=[word]%7C[pronun-des]
#   mp3 file for pronunction(e.g.ping2): http://www.mdbg.net/chindict/rsc/audio/voice_pinyin_cl_mdbg/ping2.mp3
#   js file for online page: http://www.mdbg.net/chindict/rsc/js/chindict.js?v1438504717
#   css file for online page: http://www.mdbg.net/chindict/rsc/css/style.css?v1438504717
# 

from os import path
import urllib.request
import zipfile
import re
import os
import sqlite3
import time
import io
import sys

################################################################################
# globals
#
################################################################################
ZIP_NAME = 'cedict_1_0_ts_utf-8_mdbg.zip'   #勿动
DATA_NAME = 'cedict_ts.u8'                    #解压后的数据文件名
CSS_NAME = 'mdbg.css'                       #采用CSS的样式文件名
MDX_NAME = 'CC-CEDICT.txt'                  #为MDX文件准备的源文件名
SQL_DB_NAME = 'sql_' +DATA_NAME +'.db3'
#----------------可配置------------------
HAN_SIMP_KEY = True                          #是否采用简中词条（False为繁中词条）
MERGE_SAME_KEY = True                         #是否合并相同词头的词条(False不合并)

################################################################################
# 显示下载/处理进度
#
################################################################################
def showProgress(a, b, c):  
    '''''回调函数 
    @a: 已经下载的数据块 
    @b: 数据块的大小 
    @c: 远程文件的大小 
    '''  
    per = 100.00 * a * b / c  
    if per > 100:  
        per = 100  
    print('Progress： %.2f%%\r' % per,end='')


################################################################################
# 下载数据库文件并解压
#
# urlretrieve方法直接将远程数据下载到本地。
#   参数filename指定了保存到本地的路径（如果未指定该参数，urllib会生成一个临时文件来保存数据）；
#   参数reporthook是一个回调函数，当连接上服务器、以及相应的数据块传输完毕的时候会触发该回调。
#   参数data指post到服务器的数据。
#   该方法返回一个包含两个元素的元组(filename, headers)，filename表示保存到本地的路径，header表示服务器的响应头。
################################################################################
def downloadAndExtract():
    url = 'http://www.mdbg.net/chindict/export/cedict/' +ZIP_NAME

    zip_path = ''.join([os.path.abspath(os.path.dirname(__file__)), path.sep, ZIP_NAME])
    
    # 判断是否存在本地文件，若是，判断是否与网络文件大小相等，否则重新下载
    if os.path.exists(zip_path) :
        local_size = os.path.getsize(zip_path)
        request = urllib.request.Request(url)
        resp = urllib.request.urlopen(request)
        if resp.code==200 :
            remote_size = resp.headers["content-length"]
            if local_size != int(remote_size) :
                print('---开始下载数据文件---')
                urllib.request.urlretrieve(url, zip_path, showProgress)
    else :
        print('---开始下载数据文件---')
        urllib.request.urlretrieve(url, zip_path, showProgress)
    print("download complete!")

    #将打包的文件解压 
    zf = zipfile.ZipFile(zip_path, 'r')  
    print('---开始解压数据文件---')
    zf.extract(DATA_NAME, os.path.abspath(os.path.dirname(__file__)))
    zf.close()
    data_path = ''.join([os.path.abspath(os.path.dirname(__file__)), path.sep, DATA_NAME])
    if os.path.exists(data_path) :
        print("extract complete!")
        os.remove(zip_path)
        return data_path

################################################################################
# 解析文件并渲染
#
################################################################################
def ParseAndRendering(file_name):
    
    #---创建SQL数据库文件
    sql_db_path = ''.join([os.path.abspath(os.path.dirname(__file__)), path.sep, SQL_DB_NAME])
    if os.path.exists(sql_db_path) :
        os.remove(sql_db_path)
    conn = sqlite3.connect(sql_db_path)
    #conn.isolation_level 事务隔离级：默认是需要自己commit才能修改数据库，置为None则自动每次修改都提交,否则为""
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS Items (han_simp text, han_trad text, pins text, defis text)''')
    
    #---创建MDX源文件
    mdx_path = ''.join([os.path.abspath(os.path.dirname(__file__)), path.sep, MDX_NAME])
    if os.path.exists(mdx_path) :
        os.remove(mdx_path)
    fdesc = open(mdx_path,  'a', encoding='utf-8')  # open or create file in append mode

    #---读取源文件，并：1.分析每行将其写入到SQL数据库中；2.提取独一无二的汉字Key。
    fsrc = open(file_name, "r", encoding='utf-8')
    lines = fsrc.readlines()
    count = len(lines)
    print("共有 " + str(count) +" 个原始词条！")
    index = 0
    #前一个汉字表示的Key
    pre_han = ""
    #不重复的汉字Key保存的字典
    han_keys = {}
    for line in lines:
        # remove '\n' in line end
        l = line.strip()
        
        #These are info lines at the beginning of the file
        #NOTE: Might be useful to store version #, date, etc for dictionary reference
        if l.startswith(("#", "#!")):
            continue
        else:
            # EXAMPLE INPUT LINE:   '反擊 反击 [fan3 ji1] /to strike back/to beat back/to counterattack/'
            # TRADITIONAL_HANZI SIMPLIFIED_HANZI [PINYIN] /TRANSLATION
            #Get trad and simpl hanzis then split and take only the simplified
            han_simp = l.partition('[')[0].split(' ', 1)[1].strip(" ")
            #Get trad and simpl hanzis then split and take only the traditional
            han_trad = l.partition('[')[0].split(' ', 1)[0].strip(" ")
            #Take the content in between the two brackets, all pinyin in pins string
            pins = l.partition('[')[2].partition(']')[0]
            #All definition text in defis string
            defis = l.partition('/')[2].strip('/')
            
            if MERGE_SAME_KEY :
                # get unique han keys
                if HAN_SIMP_KEY and (not (han_simp in han_keys)) :
                    han_keys[han_simp] = index
                if (not HAN_SIMP_KEY) and (not (han_trad in han_keys)) :
                    han_keys[han_trad] = index
                # Insert a row of data
                cur.execute("INSERT INTO Items(han_simp,han_trad,pins,defis) VALUES (?,?,?,?);", (han_simp,han_trad,pins,defis))
            else :
                mdx_content,pre_han = formatItem(han_simp, han_trad, pins.split(' '), defis.split('/'), pre_han)
                fdesc.write(mdx_content)
                
            showProgress(index, 1, count)
            index += 1
    # Save (commit) the changes
    conn.commit()
    cur.close()
    print("写入数据库完成！")
    
    if MERGE_SAME_KEY :
        prgs = 0
        for han in han_keys :
            if HAN_SIMP_KEY :
                cursor = conn.execute("SELECT han_simp,han_trad,pins,defis from Items where han_simp=?", (han,))
            else :
                cursor = conn.execute("SELECT han_simp,han_trad,pins,defis from Items where han_trad=?", (han,))
            for row in cursor:
                mdx_content,pre_han = formatItem(row[0], row[1], row[2].split(' '), row[3].split('/'), pre_han)
                fdesc.write(mdx_content)
                showProgress(prgs, 1, len(han_keys))
                prgs += 1
            cursor.close()
        print("合并后，共有 "+str(len(han_keys)) +" 个词条！")
        
    fdesc.write('\n</>\n')
    # We can also close the connection if we are done with it.
    # Just be sure any changes have been committed or they will be lost.
    conn.close()
    os.remove(sql_db_path)
    print("处理完成！")
    
################################################################################
# 转换单个拼音数字为真正的拼音符号
# 
# e.g. ni3 ---> nǐ
################################################################################
def pinyinize(word):
    word = word.strip()
    if word=='' :
        return word
    
    # char codes ref from: http://www.math.nus.edu.sg/aslaksen/read.shtml
    TONES = { "1a":"ā", "2a":"á", "3a":"ǎ", "4a":"à", "5a":"a",
          "1e":"ē", "2e":"é", "3e":"ě", "4e":"è", "5e":"e",
          "1i":"ī", "2i":"í", "3i":"ǐ", "4i":"ì", "5i":"i",
          "1o":"ō", "2o":"ó", "3o":"ǒ", "4o":"ò", "5o":"o",
          "1u":"ū", "2u":"ú", "3u":"ǔ", "4u":"ù", "5u":"u",
          "1v":"ǖ", "2v":"ǘ", "3v":"ǚ", "4v":"ǜ", "5v":"ü" }
    # using v for the umlauded u
    ret_string = ""
    
    # "zhong1" -> tone :'1', pinyin : 'zhong'
    if word[-1].isdigit() and len(word)>1 :
        tone = word[-1]
        pinyin = word[0:len(word)-1].lower()
        
        # 3 rules
        #   1- A and E get the tone mark if either one present (they are never both present)
        #   2- in ou, o gets the tone mark
        #   3- in all other cases, last vowel gets the tone
        # see http://pinyin.info/rules/where.html
        if pinyin.find("a") > -1:
            ret_string = pinyin.replace("a", TONES[tone+"a"])
        elif pinyin.find("u:e") > -1:
            ret_string = pinyin.replace("u:e", "ü"+TONES[tone+"e"])
        elif pinyin.find("e") > -1:
            ret_string = pinyin.replace("e", TONES[tone+"e"])
        elif pinyin.find("ou") > -1:
            ret_string = pinyin.replace("ou", TONES[tone+"o"]+"u")
        elif pinyin.find("io") > -1:
            ret_string = pinyin.replace("io", "i"+TONES[tone+"o"])
        elif pinyin.find("iu") > -1:
            ret_string = pinyin.replace("iu", "i"+TONES[tone+"u"])
        elif pinyin.find("ui") > -1:
            ret_string = pinyin.replace("ui", "u"+TONES[tone+"i"])
        elif pinyin.find("uo") > -1:
            ret_string = pinyin.replace("uo", "u"+TONES[tone+"o"])
        elif pinyin.find("i") > -1:
            ret_string = pinyin.replace("i", TONES[tone+"i"])
        elif pinyin.find("o") > -1:
            ret_string = pinyin.replace("o", TONES[tone+"o"])
        elif pinyin.find("u:") > -1:
            ret_string = pinyin.replace("u:", TONES[tone+"v"])
        elif pinyin.find("u") > -1:
            ret_string = pinyin.replace("u", TONES[tone + "u"])
        else:
            ret_string = pinyin
         
        #恢复原始声母的大小写状态
        if word[0].isupper() :
            ret_string = ret_string[0].capitalize() + ret_string[1:]
    else:
        #非拼音的纯字母，如'A' -> 'A'
        ret_string = word
        
    return ret_string
    
################################################################################
# 格式化单个词条 
# 
# 1.解释里的跳转和拼音例子：
#   "口快心直 口快心直 [kou3 kuai4 xin1 zhi2] /see 心直口快[xin1 zhi2 kou3 kuai4]/"
#   "古田 古田 [Gu3 tian2] /Gutian county in Ningde 寧德|宁德[Ning2 de2], Fujian/"
#   "嗩吶 唢呐 [suo3 na4] /also written 鎖吶|锁呐/also called 喇叭[la3 ba5]/
#   "一甲 一甲 [yi1 jia3] /1st rank or top three candidates who passed the imperial examination (i.e. 狀元|状元[zhuang4 yuan2], 榜眼[bang3 yan3], and 探花[tan4 hua1], respectively)/"
#   "啤酒 啤酒 [pi2 jiu3] /beer (loanword)/CL:杯[bei1],瓶[ping2],罐[guan4],桶[tong3],缸[gang1]/"
#   "B超 B超 [B chao1] /B-mode ultrasonography/prenatal ultrasound scan/abbr. for B型超聲|B型超声[B xing2 chao1 sheng1]/"
#   "三略 三略 [San1 lu:e4] /see 黃石公三略|黄石公三略[Huang2 Shi2 gong1 San1 lu:e4]/"
#   “丈二金剛摸不著頭腦 丈二金刚摸不着头脑 [zhang4 er4 Jin1 gang1 mo1 bu5 zhao2 tou2 nao3] /see 丈二和尚，摸不著頭腦|丈二和尚，摸不着头脑[zhang4 er4 he2 shang5 , mo1 bu5 zhao2 tou2 nao3]/”
# 特例: '中括號 中括号 [zhong1 kuo4 hao4] /square brackets [ ]/'
#
# 2.观察到以上例子一般有如下规律：
#   ‘繁|简[拼音]’ 或 ‘简[拼音]’ 或 ‘繁|简’ 或 ‘[拼音]’：四种情况。
#   同时要注意单个例句中的多次跳转！
################################################################################
def formatItem(han_simp, han_trad, pin, defi, pre_han):
    result = ''
    han = ''
    
    #------
    #   苹果电脑
    #   <link rel="stylesheet" type="text/css" href="mdbg.css"/>
    #   <div class="hz">
    #       <span class="ht2">苹</span><span class="ht3">果</span><span class="ht4">电</span><span class="ht3">脑</span>
    #   </div>
    #   <div class="py">
    #       <span class="pt2">Píng</span><span class="pt3">guǒ</span><span class="pt4">diàn</span><span class="pt3">nǎo</span>
    #   </div>
    if HAN_SIMP_KEY :
        han = han_simp
    else :
        han = han_trad

    i_head = han +'\n'
    i_style = '<link rel="stylesheet" type="text/css" href="'+CSS_NAME+'"/>'
    i_hz = '<div class="hz">'
    i_py = '<div class="py">'
    index = 0
    for p in pin :
        if p[-1].isdigit() and len(p)>1 :
            tone = p[-1]
        else :
            tone = '5'
        i_hz += '<span class="ht'+tone+'">'+i_head[index]+'</span>'
        i_py += '<span class="pt'+tone+'">'+pinyinize(p)+'</span>'
        index += 1
    i_hz += '</div>'
    i_py += '</div>'
    
    #   <div class="dy">
    #       <ul>
    #           <li> Apple computer</li>
    #           <li> Mac  </li>
    #           <li> Macintosh </li>
    #       </ul>
    #   </div>
    #   </>
    i_dy = '<div class="dy"><ul>'
    for d in defi :
        d = d.strip()
        
        # ‘汉字[拼音]’ -> '跳转'
        pattern2 =re.compile(r'(?P<before>[,:\(\)\s]+)(?P<han>[a-zA-Z1-5,\u2E80-\u9FFF]+)(?P<pinyin>\[[a-zA-Z1-5\s:,]+\])')
        d = pattern2.sub(r'\g<before><a href="entry://\g<han>">\g<han></a>\g<pinyin>', d)
        
        # ‘繁|简[拼音]’ 或 ‘繁|简’ -> '跳转'
        pattern1 =re.compile(r'(?P<before>[,:\(\)\s]+)(?P<t_han>[a-zA-Z1-5,\u2E80-\u9FFF]+)(?:\|(?P<s_han>[a-zA-Z1-5,\u2E80-\u9FFF]+))(?P<after>[\[,.:\(\)\s]+)')
        if HAN_SIMP_KEY :
            d = pattern1.sub(r'\g<before><a href="entry://\g<s_han>">\g<s_han></a>\g<after>', d)
        else :
            d = pattern1.sub(r'\g<before><a href="entry://\g<t_han>">\g<t_han></a>\g<after>', d)

        # ‘繁|简[拼音]’ 或 ‘简[拼音]’ 或 ‘[拼音]’ -> '拼音符号'
        # \[([a-zA-Z:]+[1-5]*\s)*([a-zA-Z:]+[1-5]*)\] 或 \[(\s*[a-zA-Z:]+[1-5]*)+\]
        res = ""
        split_res = re.split(r'(\[[a-zA-Z1-5\s:,]+\]*)', d)
        pattern3 =  re.compile(r'(\[(?P<pinyin>[a-zA-Z1-5\s:,]+)\])')
        for s in split_res :
            if s!=None :
                sresult = re.search(pattern3, s)
                if sresult :
                    # pinyin for other entry
                    if sresult.group('pinyin') != None :
                        dpy = sresult.group('pinyin').split(" ")
                        ddpy = '['
                        for dp in dpy :
                            ddpy += pinyinize(dp)+' '
                        ddpy = ddpy.strip() +']'
                    else :
                        ddpy = ""
                    s = pattern3.sub(ddpy, s)
            else :
                continue
            res +=s
        i_dy += '<li>'+res+'</li>'
    i_dy += '</ul></div>'
    
    if pre_han != "" :
        i_tail ='\n</>\n'
    else :
        i_tail =''
    if MERGE_SAME_KEY :
        i_hz = '<div class="hz">'+han+'</div>'
    if MERGE_SAME_KEY and han==pre_han :
        result += i_py + i_dy
    else :
        result += i_tail + i_head + i_style + i_hz + i_py + i_dy
    return result,han

if __name__ == "__main__":  
    start = time.time() 
#    sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding='gb18030') #改变标准输出的默认编码
    
    data_path = downloadAndExtract()
#    data_path ="./"+DATA_NAME
    ParseAndRendering(data_path)

    end = time.time() 
    waste_time = str(end - start)
    print("耗时: %s 秒！" % (waste_time))

#	input("请按回车键继续……")
    os.system('pause')


