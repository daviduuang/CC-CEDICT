# CC-CEDICT

CC-CEDICT词典渲染工具及文件夹说明

关于MDict格式、Windows下的词典软件及生成工具MdxBuilder可以到这里[下载](http://www.octopus-studio.com/download.cn.htm)

0. 运行环境

环境：Python 3.4.

1. 文件夹说明

output  : 存放已制作好的词典文件，按制作日期存放，可以直接下载使用
data    : 存放排版所用CSS样式文件

2. 文件说明
CC-CEDICT.py  ：下载CC-CEDICT数据文件，解压，解析数据文件并渲染成符合MDICT(HTML)格式的文件
                默认为简体中文索引，修改“HAN_SIMP = True ”为'False', 即可切换为繁体中文索引
<<<<<<< HEAD
Changes.txt   ：程序和数据更新说明
​
=======
Changes.txt   ：程序和数据更新说明


>>>>>>> origin/master
3. 工具使用方法
  0. 确保以上运行环境
  1. 运行 CC-CEDICT.py 生成用于MdxBuilder制作的源文件（html）
  2. 运行 MdxBuilder ：
    Source 选 ‘4.’中生成的CC-CEDICT.txt的路径；
    Target 选择 ‘output’ 文件夹下自己指定的文件名（推荐名称CC-CEDICT.mdx）；
    Data 选 前面存放排版样式的‘data’文件夹；
    OriginalFormat选MDict（Html），Encoding选UTF-8（Unicode），Title填CC-CEDICT，Description随便填（可参考DictInformation.txt）；
    点击Start按钮，等待处理结束  
<<<<<<< HEAD
  3. 在支持MDict格式词典的软件中添加生成的CC-CEDICT.mdx和CC-CEDICT.mdd
​
​
=======
  3. 在支持MDict格式词典的软件中添加生成的CC-CEDICT.mdx和CC-CEDICT.mdd
  

>>>>>>> origin/master
