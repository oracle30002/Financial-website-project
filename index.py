from flask import Flask, render_template, request, g, redirect
import sqlite3
import requests
import math
import matplotlib.pyplot as plt
import matplotlib
import os
matplotlib.use('agg')

app = Flask(__name__)
database = 'datafile.db'
# 連接sqlite3資料庫
def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = sqlite3.connect(database)
    return g.sqlite_db

@app.teardown_appcontext
def close_connection(exception):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route('/')
def home():
    #在首頁除了要連到index外，還要能顯示現金的庫存狀況
    conn = get_db()
    cursor = conn.cursor() 
    result = cursor.execute("select * from cash") #要從資料庫內提取資料，用SQL語法
    cash_result = result.fetchall()  #將cash的內容fetch到cash_result的變數
    #計算台幣與美金的總額
    taiwanese_dollars = 0
    us_dollars = 0
    for data in cash_result:
        taiwanese_dollars += data[1]
        us_dollars += data[2]
    #獲取匯率資訊
    r = requests.get('https://tw.rter.info/capi.php')
    currency = r.json()   #可以用print(currency)來看所需要的資料，我們需要['USDTWD']['Exrate']
    total = math.floor(taiwanese_dollars + us_dollars * currency['USDTWD']['Exrate'])

    #取得股票資訊(從SQL資料庫中提取)
    result2 = cursor.execute("select * from stock")
    stock_result = result2.fetchall()
    unique_stock_list = []  #我們希望相同的股票直接加總，而非一筆筆呈現
    for data in stock_result: 
        if data[1] not in unique_stock_list:
            unique_stock_list.append(data[1]) #將獨特股票加入list中並計算單一比股票的數據
    #計算股票總市值
    total_stock_value = 0

    #計算單一股票資訊(將之儲存在一個list中)
    stock_info = []  
    for stock in unique_stock_list:
        result = cursor.execute(
            "select * from stock where stock_id =?", (stock, ))
        result = result.fetchall()
        stock_cost = 0 #單一股票總花費
        shares = 0 #單一股票的股數
        for d in result:
            shares += d[2]
            stock_cost += d[2] * d[3] + d[4] + d[5]
        #取得目前股價(從證交所API)
        url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&stockNo=" + stock
        response = requests.get(url) #將url的資料用response接收
        data = response.json() #將json檔案的資料存入data變數中，並印出data來判別所需要使用的數據
        price_array = data['data'] #data是一個list裡面有存放price
        value = price_array[len(price_array) - 1][6] #將data list中最後一項的第七個值取出，放入變數
        clean_value = value.replace(',', '') #因為破千有逗號，要先清除逗號才能轉浮點數
        current_price = float(clean_value)
        # 單一股票總市值
        total_value = round(current_price * shares)
        total_stock_value += total_value
        # 單一股票平均成本(計算到小數點第二位)
        average_cost = round(stock_cost / shares, 2)
        # 單一股票報酬率(計算百分比)
        rate_of_return = round((total_value - stock_cost) * 100 / stock_cost, 2)
        #將所有剛剛單一個股計算的各項值加入stock_info中
        stock_info.append({'stock_id': stock, 'stock_cost': stock_cost, 
                           'total_value': total_value, 'average_cost': average_cost,
                           'shares': shares, 'current_price': current_price, 
                           'rate_of_return': rate_of_return})

    for stock in stock_info:
        stock['value_percentage'] = round(stock['total_value'] * 100 / total_stock_value, 2)


    #繪製出股票圓餅圖(利用Matplotlib)，先確認unique_stock_list = [] 內是否有數據
    if len(unique_stock_list) != 0:
        labels = tuple(unique_stock_list)
        sizes = [d['total_value'] for d in stock_info]   #從stock_info中找到每一筆total_value值
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.pie(sizes, labels=labels, autopct=None, shadow=0)
        fig.subplots_adjust(top=1, bottom=0, right=1,
                            left=0, hspace=0, wspace=0)
        #用上面步驟就能繪製出圖表，但是要將其存在一個叫做static的資料夾內(為template能使用的)
        plt.savefig("static/piechart.jpg", dpi=200)
    else:
        try:
            os.remove('static/piechart.jpg')
        except:
            pass


    #繪製股票現金圓餅圖
    if us_dollars != 0 or taiwanese_dollars != 0 or total_stock_value != 0:
        labels = ('USD', 'TWD', 'Stock')
        sizes = (us_dollars * currency['USDTWD']['Exrate'],
                 taiwanese_dollars, total_stock_value)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.pie(sizes, labels=labels, autopct=None, shadow=None)
        fig.subplots_adjust(top=1, bottom=0, right=1,
                            left=0, hspace=0, wspace=0)
        plt.savefig("static/piechart2.jpg", dpi=200)
    else:
        try:
            os.remove('static/piechart2.jpg')
        except:
            pass



    #在data中加入是否顯示圖片的資訊
    #最後將stock_info的資訊加入data內
    #現在有所有欄位所需要的資料，製作一個物件，裡面是所有要帶入的數值
    data = {'show_pic_1': os.path.exists('static/piechart.jpg'), 'show_pic_2': os.path.exists('static/piechart2.jpg'),
            'total': total, 'currency': currency['USDTWD']['Exrate'], 'ud': us_dollars, 
            'td': taiwanese_dollars, 'cash_result': cash_result, 'stock_info': stock_info} #利用cash_result來接這個物件
    #最後將物件傳入index.html中
    return render_template('index.html', data=data)

#-----------------------------------------------------------------------
#現金庫存表單項目

@app.route('/cash')
def cash_form():
    return render_template('cash.html')

# 這個route會接收cash的表單內容，用的是method='POST'，在http協議中，要對伺服器
# 提交資料，則可以使用POST method。
@app.route('/cash', methods=['POST'])
def submit_cash():
    #取得金額與日期資料
    #若不為空字串，則將資料分配給相對應的變數
    if request.values['taiwanese-dollars'] != '':
        taiwanese_dollars = request.values['taiwanese-dollars']
    if request.values['us-dollars'] != '':
        us_dollars = request.values['us-dollars']
    note = request.values['note']
    date = request.values['date']

    #更新數據庫資料
    conn = get_db()
    cursor = conn.cursor()
    #以下執行會利用SQL語法將資料寫入db_setting的表個欄位內，而values後面接四個問號，就是會帶入上面四個相應變數
    cursor.execute("""insert into cash (taiwanese_dollars, us_dollars, note, date_info) values (?, ?, ?, ?)"""
                   , (taiwanese_dollars, us_dollars, note, date))
    conn.commit() #要將執行完結果給commit
    #將使用者導回主頁面(利用redirect的module)
    return redirect("/")

#建立一個route會接收index.html裡面的刪除request，並連接資料庫將資料刪除
@app.route('/cash-delete', methods=['POST'])
def cash_delete():
    transaction_id = request.values['id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""delete from cash where transaction_id=?""",
                   (transaction_id, ))
    conn.commit()
    return redirect("/")

#----------------------------------------------------------------------------
#股票庫存表單項目

@app.route('/stock')
def stock_form():
    return render_template('stock.html')

@app.route('/stock', methods=['POST'])
def submit_stock():
    #用request來獲取stock.html上用戶輸入的資料
    stock_id = request.values['stock-id']
    stock_num = request.values['stock-num']
    stock_price = request.values['stock-price']
    processing_fee = 0  #因為processing_fee使用者不一定會填，故設個條件來獲取
    tax = 0
    if request.values['processing-fee'] != "":
        processing_fee = request.values['processing-fee']
    if request.values['tax'] != "":
        tax = request.values['tax']
    date = request.values['date']

    #將網頁上使用者輸入的資料更新至資料庫中
    conn = get_db()
    cursor = conn.cursor()
    #以下執行會利用SQL語法將資料寫入db_setting的表個欄位內，而values後面接六個問號，就是會帶入後面tuple中的六個變數值
    cursor.execute("""insert into stock (stock_id, stock_num, stock_price, processing_fee, tax, date_info) values (?, ?, ?, ?, ?, ?)"""
                   , (stock_id, stock_num, stock_price, processing_fee, tax, date))
    conn.commit() #要將執行完結果給commit
    #將使用者導回主頁面
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
