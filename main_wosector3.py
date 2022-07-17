from datetime import datetime
from tkinter import HORIZONTAL
from tkinter import VERTICAL
import streamlit as st
from PIL import Image
import numpy as np
import pandas as pd
import toml
from streamlit_option_menu import option_menu
import yfinance as yf
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import csv
import mysql.connector as msc
import re
import plotly.express as px

db = msc.connect(host="localhost", user="root",
                 passwd="root", database="testdatabase")
cur = db.cursor(buffered=True)


def getAllStocks():
    ls = []
    query = """
    select symbol from stock_info
    """
    cur.execute(query)
    ls = [i[0] for i in cur]
    return ls
def generatePD(d):
    di = {}
    sym = [str(i[0]) for i in d]
    di['symbol'] = sym
    date = [i[3] for i in d]
    di['Date'] = date
    vol = [int(i[1]) for i in d]
    di['Volume'] = vol
    price = [float(i[2]) for i in d]
    di['Price'] = price
    df = pd.DataFrame(di)
    return df


def execQ(query, val):
    try:
        cur.execute(query, val)
        db.commit()
    except:
        print("DB Error")
    finally:
        return cur.fetchall()


def getStockQty(username, sym):
    qty = 0
    try:
        query = """
        select qty from current_stocks where username = %s and symbol= %s"""
        val = (username, sym)
        cur.execute(query, val)
        db.commit()
        ls = cur.fetchall()
        if(len(ls) > 0):
            qty = ((ls)[0])[0]
    except:
        print("Getting Stock Quantity Error")
        qty = 0
    return qty


def getUsernames():
    ls = []
    try:
        cur.execute("select username from user_login")
        for i in cur:
            ls.append(".".join(i))
    except:
        print("DB Error")
    finally:
        return ls


class User:
    def __init__(self, uname):
        self.uname = uname
        self.cur = db.cursor(buffered=True)
        try:
            self.cur.execute(
                "select fullname,mobilenum,email_id,balance from user_login where username=%s and 1 = %s", (self.uname, 1))
            tup = ()
            for i in self.cur:
                tup = i
        except:
            tup = ("", "", "", 0)
            print("DB Error")
        finally:
            self.fname, self.moNum, self.eid, self.balance = tup
            self.balance = float(self.balance)

    def addBalance(self, amt):
        self.balance += amt
        self.updateDB()

    def updateDB(self):
        try:
            query = "update user_login set mobilenum = %s, email_id = %s, balance = %s where username = %s"
            val = (self.moNum, self.eid, self.balance, self.uname)
            self.cur.execute(query, val)
            db.commit()
        except:
            print("Updation into DataBase Error")

    def toDict(self):
        d = {}
        try:
            self.cur.execute(
                "select username,fullname,mobilenum,email_id,balance from user_login where username=%s and 1 = %s", (self.uname, 1))
            for i in self.cur:
                d[i[0]] = list(i[1:])
        except:
            print("DB Error")
        return d

    def getCurrentStocks(self):
        tups = []
        #sym  = [],tups
        try:
            query = """
            select symbol from current_stocks where username = %s and 1 = %s
            """
            val = (self.uname, 1)
            self.cur.execute(query, val)
            for i in self.cur:
                t = ".".join(i)
                tups.append(t)

            # print(tups)
        except:
            print("Getting Stocks Error")
            tups = []
        finally:
            return tups

    def getWatchList(self):
        ls = []
        try:
            query = """
            select symbol from watchlist where username= %s and 1 = %s
            """
            val = (self.uname, 1)
            self.cur.execute(query, val)
            ls = [i[0] for i in self.cur.fetchall()]
            db.commit()
        except:
            print("Getting Watchlist Error")
        finally:
            return ls

    def BuyStocks(self, sym, qty):
        
        df  = yf.download(sym,period="1d",interval="1m")
        cp = float(df.tail(1).iloc[0,3])
        #cp = 3164.40
        if((cp * qty) <= self.balance):
            if(sym in self.getCurrentStocks()):
                try:
                    query = """
                    update current_stocks
                    set  bp = (bp*qty + %s)/(qty + %s),
                    qty = qty + %s
                    where symbol = %s and username = %s
                    """
                    val = (cp*qty,qty,qty,sym, self.uname)
                    self.cur.execute(query, val)
                    db.commit()
                except:
                    print("Updation Error")
            else:
                try:
                    query = """
                    insert into current_stocks(username,symbol,bp,qty) 
                    values(%s,%s,%s,%s)
                    """
                    val = (self.uname, sym, cp, qty)
                    self.cur.execute(query, val)
                    db.commit()
                except:
                    print("Insertion into Current Stocks Error")
            self.addBalance(-(cp*qty))
            self.updateDB()
            try:
                query = """
                insert into transaction(username,symbol,action,volume,price)
                values(%s,%s,%s,%s,%s)
                """
                val = (self.uname, sym, "buy", qty, cp)
                self.cur.execute(query, val)
                db.commit()
                # execQ(query,val)
            except:
                print("Insertion into Transaction Error")

        else:
            return -1

    def addtoWatchList(self, sym):
        if(sym in self.getWatchList()):
            return -1
            #print("{0} already in watchlist".format(sym))
        else:
            try:
                query = """
                insert into watchlist values (%s,%s)
                """
                val = (self.uname, sym)
                self.cur.execute(query, val)
                db.commit()
            except:
                print("Insertion into watchlist error")
            finally:
                return 1

    def removeFromWatchlist(self, sym):
        if(sym in self.getWatchList()):
            try:
                query = """
                delete from watchlist where username= %s and symbol = %s
                """
                val = (self.uname, sym)
                self.cur.execute(query, val)
                db.commit()
            except:
                print("Deletion From Watchlist Error")
        else:
            print("{0} does not exist in watchlist".format(sym))

    def sellStock(self, sym, qty):
        df  = yf.download(sym,period="1d",interval="1m")
        cp = float(df.tail(1).iloc[0,3])
        #cp = 5000
        if(sym in self.getCurrentStocks()):
            if(qty <= getStockQty(self.uname, sym)):
                query = """
                select bp from current_stocks where username = %s and symbol= %s"""
                val = (self.uname, sym)
                self.cur.execute(query, val)
                stp = float(((self.cur.fetchall())[0])[0])
                if(qty == getStockQty(self.uname, sym)):
                    query = """
                    delete from current_stocks where username = %s and symbol = %s
                    """
                    val = (self.uname, sym)
                    self.cur.execute(query, val)
                    db.commit()
                else:
                    query = """
                    update current_stocks
                    set qty = qty - %s
                    where symbol = %s and username = %s
                    """
                    val = (qty, sym, self.uname)
                    self.cur.execute(query, val)
                    db.commit()
                query = """
                insert into transaction(username,symbol,action,volume,price,pl)
                values(%s,%s,%s,%s,%s,%s)
                """
                val = (self.uname, sym, 'sell', qty, cp, qty*(cp-stp))
                cur.execute(query, val)
                db.commit()
                self.addBalance(qty*cp)
                self.updateDB()
            else:
                print("You Do not have those many stocks")
        else:
            print(sym + " not held by User")

    def generateReport(self):
        d = {}
        try:
            query = """
            select symbol,volume,price,trans_time from transaction where action = %s and username = %s
            """
            val = ("buy", self.uname)
            self.cur.execute(query, val)
            d['buy'] = self.cur.fetchall()
            query = """
            select symbol,volume,price,trans_time,pl from transaction where action = %s and username = %s
            """
            val = ("sell", self.uname)
            self.cur.execute(query, val)
            d['sell'] = self.cur.fetchall()

        except:
            print("Generating Report Error")
        finally:
            return d
    def printWatchlist(self):
        ls = self.getWatchList()
        d={}
        ls1 = []
        ls2 = []
        ls3 = []
        query= """
        select * from stock_info where symbol = %s and 1= %s"""
        if(len(ls)>0):
            
            d['Symbol'] = ls
            for i in ls:
                #ls1.append(((yf.Ticker(i)).info)['regularMarketPrice'])
                df  = yf.download(i,period="1d",interval="1m")
                ls1.append(float(df.tail(1).iloc[0,3]))
                val = (i,1)
                self.cur.execute(query,val)
                for i in self.cur:
                    sname = i[1]
                    sect = i[-1]
                    ls2.append(sname)
                    ls3.append(sect)
            d['Name'] = ls2
            d['Sector'] = ls3
            d['Current Price (Rs)'] = ls1
            print(d)
            return pd.DataFrame(d)
        else:
           return pd.DataFrame(d)
    def getCurrentBalance(self):
        query = """
        select balance from user_login where username = %s and 1 = %s"""
        val = (self.uname,1)
        self.cur.execute(query,val)
        return float((self.cur.fetchall())[0][0])
    def getPortfolio(self):
        query="""
        select symbol,bp,qty from current_stocks where username = %s and 1 = %s"""
        val = (self.uname,1)
        self.cur.execute(query,val)
        d={}
        ls,ls1,ls2,ls3  = [],[],[],[]
        for i in self.cur.fetchall():
            ls.append(i[0])
            ls1.append(float(i[1]))
            ls2.append(int(i[2]))
            cp = (yf.download(tickers=i[0],period="1d",interval="1m").tail(1)).iloc[0,3]
            ls3.append(cp)
            
        d['Stock'] = ls
        d['Buying Price'] = ls1
        d['Quantity'] = ls2
        d['Current Price'] = ls3
        df = pd.DataFrame(d)
        #df = pd.DataFrame(self.cur.fetchall(),columns=['Stock','Buying Price','Quantity'])
        df['Investment Value'] = df['Buying Price'] * df['Quantity']
        df['Unrealized P/L'] = (df['Current Price'] * df['Quantity'])-df['Investment Value']
        return df
        
         


class NewUser(User):
    def __init__(self, uname, fullname, pswd, mobileNum, email_id):
        self.cur = db.cursor(buffered=True)
        self.uname = uname
        self.fullname = fullname
        self.pswd = pswd
        self.mobileNum = mobileNum
        self.email_id = email_id
        self.balance = 0

        query = "insert into user_login(username,fullname,pswd,mobilenum,email_id) values(%s,%s,%s,%s,%s)"
        val = (self.uname, self.fullname, self.pswd,
               self.mobileNum, self.email_id)
        self.cur.execute(query, val)
        db.commit()

    def __str__(self):
        str = self.uname + "\n" + self.fullname + "\n" + \
            self.pswd + "\n" + self.mobileNum + "\n"
        return str

# if st.session_state['C_User']=="":
#     pass
# else:
#     st.session_state['C_User']    
#     C_User = User("dp2307")


#uname = "bhargav"
st.set_page_config(layout="wide")

with open("E:\\College\\Documents\\PSC\\Innovative\\styles.css") as f:
    st.markdown('<style>{}</style>'.format(f.read()), unsafe_allow_html=True)


if 'key' not in st.session_state:
    st.session_state['key'] = False
if(st.session_state['key'] != True):
    heading="<div class='heading1'>Welcome to Stockly.com!</div>"
    st.markdown(heading,unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    col1, col2, col3 = st.columns([1, 4, 1])
    choice = option_menu("",["Login", "Signup"],orientation=HORIZONTAL)
    if (choice == "Login"):
        Email_id = st.text_input("Username: ")
        password = st.text_input("Password:", type="password")
        if st.button("Login"):
            query="""select * from user_login where username = %s and pswd = %s"""
            val=(Email_id,password)
            cur.execute(query,val)
            if(len(cur.fetchall()) == 0):
                st.error("Invalid Login Credentials")
            else: 
                st.success("Login Successful")
                st.session_state['C_User'] = Email_id

                #global C_User 
                #C_User = User(Email_id)
                #uname= Email_id
                st.session_state['key'] = True
            # os.system('streamlit run E:\College\Documents\PSC\Innovative\main_wosector.py ')        
    else:
            n_V=em_V=mo_V=Pass_V=CPass_V=False

            name = st.text_input("Full Name : ")
            if(n_V==False and len(name)>0):            
                if(len(name)>=30 or re.search(r'\d', name)):                
                    st.warning("Invalid format for name")
                else:
                    n_V=True
            Email = st.text_input("Mail ID : ")
            if(em_V==False and len(Email)>0):            
                if(not Email.endswith("@gmail.com")):                
                    st.warning("Invalid format for Email")
                else:
                    em_V=True
            mobile = st.text_input("Mobile Number : ")
            if(mo_V==False and len(mobile)>0):            
                if(len(mobile)!=10):                
                    st.error("Invalid format for Mobile number(Only 10 Digits are allowed)")
                else:
                    mo_V=True
            passwd = st.text_input("Password : ",type="password")
            if(Pass_V==False and len(passwd)>0):            
                if(len(passwd)<8 or not any(ele.isupper() for ele in passwd) or not any(ele.islower() for ele in passwd) or not any(ele.isdigit() for ele in passwd)):                
                    st.error("Password is not valid as per Specified format")
                else:
                    Pass_V=True
                    st.success("Password Verified")
            Pass_Ins = """<div class="Pass_Ins"><h3>Requirements : </h2><ul tyoe="disc"><li>Minimum length : 8</li><li>1 Upper case letter</li><li>1 Lower case letter</li><li>Atleast one digit</li></ul></div>"""
            st.markdown(Pass_Ins,unsafe_allow_html=True)
            c_passwd = st.text_input("Confirm Password:",type="password")
            if(CPass_V==False and len(c_passwd)>0):            
                if(c_passwd != passwd):                
                    st.error("Password doesn't match")
                else:
                    CPass_V=True
            agree = st.checkbox("I agree to all the terms and conditions!")
            if agree:
                signup = st.button("Signup!")
                if n_V and em_V and mo_V and Pass_V and CPass_V :
                    if signup:
                        st.success("Congratulations "+name+", you have signed up Successfully!")
                        user1 = NewUser(Email,name,passwd,mobile,Email)
                    #uname=Email_id
                else:
                    st.error("Entered data is not verified")

else:
    C_User = User(st.session_state['C_User'])
    #C_User.toDict()
    c2 = "<div class='heading1'>Welcome back , "+C_User.fname+" </div>"
    st.markdown(c2, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    #col1, col2, col3 = st.columns([1, 4, 1])
    choice = option_menu("",["Analysis", "Search", "Watchlist", "My PortFolio"],orientation=HORIZONTAL)
    if choice == "Analysis":
        
        stock = getAllStocks()
        x = st.multiselect("Select Your Stocks:",getAllStocks())
        c11,c12 = st.columns(2)
        with c11:
            start_date=st.date_input("Select the start date: ")
        with c12:    
            end_date=st.date_input("Select the last date: ")
        # data = yf.download(tickers=x, period ='5d', interval = '15m', rounding= True)
        #data=yf.Ticker(x)
        #print("-"+x+"-"+avlbl1)
        if(len(x)!= 0 ):
            days = (end_date - start_date).days
            fig, ax = plt.subplots()
            ax.set(ylabel="Price")
            #ax.hist(arr, bins=20)
            vals = []
            if(days == 0):
                
                for i in x:
                    df = yf.download(tickers=i,period="1d",interval="1m")
                    ls = [i  for i in (df['Close'])]
                    vals.append(ls)
                for i in range(len(vals)):
                    ax.plot(vals[i],label=x[i])
                #ax.title("Comparison between {0}".format(". ".join(list(x))))
                ax.title.set_text('{0} on {1}'.format(",".join(list(x)),start_date))
                ax.set(xlabel="Minutes")
                ax.legend()
                st.pyplot(fig)      
            else:
                for i in x:
                    df = yf.download(tickers=i,start=start_date,end=end_date)
                    # xt = [i.strftime("%d") for i in df.index]
                    ls = [i  for i in (df['Close'])]
                    vals.append(ls)
                for i in range(len(vals)):
                    ax.plot(vals[i],label=x[i])
                #ax.title("Comparison between {0}".format(". ".join(list(x))))
                ax.title.set_text('{0} between {1} and {2}'.format(",".join(list(x)),start_date,end_date))
                ax.set(xlabel="Date")
                ax.legend()
                st.pyplot(fig)
                    
                    
                    
            #st.write((end_date - start_date).days)
            #print(type(end_date - start_date))
    elif choice=="Search":
        stock = getAllStocks()
        Sname = st.selectbox("Search your Stock Here: ",[""]+stock)
        
        if(Sname!=""):

            c21,c22 = st.columns([2,6])
            with c21:            
                opt = option_menu("", ["Add to Watchlist","Buy This Stock", "Watch more Info"],orientation=VERTICAL,default_index=-1)
            with c22:
                if opt=="Add to Watchlist":
                    if(C_User.addtoWatchList(Sname)==-1):
                        st.markdown("<div class='warn'><p class='warn_msg'>"+Sname+" is already there in Watchlist</p></div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='su'><p class='su_msg'>"+Sname+" Successfully added to Watchlist</p></div>", unsafe_allow_html=True)

                elif opt == "Buy This Stock":
                    Sqty = st.number_input("Quantity : ",min_value=0,max_value=100,step=1)
                    if(Sqty>0):
                        if(C_User.BuyStocks(Sname, Sqty) ==-1):
                            st.markdown("<div class='er'><p class='er_msg'>"+Sname+" Insufficient Balance</p></div>", unsafe_allow_html=True)
                        else:
                            st.markdown("<div class='su'><p class='su_msg'>"+str(Sqty)+" Of "+Sname +" bought Successfully</p></div>", unsafe_allow_html=True)

                elif opt == "Watch more Info":
                    query="""
                    select shortname,longname,sector from stock_info where symbol = %s and 1= %s"""
                    cur.execute(query,(Sname,1))
                    k = [str(i) for i in (cur.fetchall())[0]]
                    ls = ['SHORT-NAME','LONG-NAME','SECTOR']
                    final = """<table class='Final' align="center">"""
                    for i in range(len(ls)):
                        final += "<tr><td class='value'>"+str(ls[i])+"</td><td>" + str(k[i]) + "</td></tr>"
                    df  = yf.download(Sname,period="1d",interval="1m")
                    final += "<tr><td class='value'>CURRENT-VALUE</td><td>" + str(float(df.tail(1).iloc[0,3])) + "</td></tr></table>"
                    st.markdown(final, unsafe_allow_html=True) 
                    ticker = yf.Ticker(Sname)
                    fin = ticker.financials
                    df = pd.DataFrame(fin.loc['Total Revenue'])
                    df = df.reset_index()
                    df = df.rename(columns={"":"Date"})
                    df1 = ((fin.loc['Gross Profit']).reset_index()).rename(columns={"":"Date"})
                    df2 = ((fin.loc['Net Income']).reset_index()).rename(columns={"":"Date"})
                    #arr = np.array((df),dtype="float")/10000000
                    #year = [i.strftime("%Y") for i in df.index]
                    fig = px.bar(df, x='Date', y='Total Revenue',title="Total Revenue")
                    st.plotly_chart(fig, use_container_width=True)
                    fig1 = px.bar(df1,x="Date",y="Gross Profit",title="Gross Profit")
                    st.plotly_chart(fig1, use_container_width=True)
                    fig2 = px.bar(df2,x="Date",y="Net Income",title="Net Income")
                    st.plotly_chart(fig2, use_container_width=True)

    elif(choice=="Watchlist"):    
        Uwatch = C_User.printWatchlist()
        if(len(Uwatch)==0):
            st.markdown("<div class='warn'><p class='warn_msg'>No Stocks in Watchlist</p></div>", unsafe_allow_html=True)
        else:
            from pandas import set_option
            Uwatch.style.apply(lambda x: "background-color: red")
            st.dataframe(Uwatch,width=700,height=800)
        x = st.multiselect("Remove Stocks :",C_User.getWatchList())
        if st.button("Confirm"):
            st.markdown("<div class='su'><p class='su_msg'>"+str(",".join(list(x)))+" Removed from watchlist</p></div>", unsafe_allow_html=True)
            for i in x:
                C_User.removeFromWatchlist(i)

    elif(choice=="My PortFolio"): 
        

        c31,c32 = st.columns([2,6])
        with c31:
            opt = option_menu("", ["Current Stocks","Current Balance","Sell","View/Download Transactions"],orientation=VERTICAL)
        with c32:
            if(opt == "Current Balance"):
                if 'C_bl_'+C_User.uname not in st.session_state:
                    st.session_state['C_bl_'+C_User.uname] = C_User.balance
                st.markdown("<h1 class='CurB'>Current Balance : <span class='CurB_Am'>"+"Rs. " + str(st.session_state['C_bl_'+C_User.uname])+"</span></h1>", unsafe_allow_html=True)
                st.markdown("\n\n")
                AddM = st.button("Add Money")
                if st.session_state.get('button') != True:
                    st.session_state['button'] = AddM
                if st.session_state['button'] == True:
                    Ex_Am = st.number_input("Amount : ")
                    
                    if st.button("Confirm"):
                        st.session_state['button'] = False
                        st.session_state['C_bl_'+C_User.uname] += Ex_Am
                        C_User.addBalance(float(Ex_Am))
                        st.markdown("<div class='su'><p class='su_msg'>"+str(Ex_Am)+" Successfully added in Your account</p></div>", unsafe_allow_html=True)
        
            elif(opt == "Sell"):
                li = C_User.getCurrentStocks()
                Sname = st.selectbox("Enter Stock you want to sell : ",[""]+li)
                if(Sname!=""):
                    #C_Pr = 10
                    C_Pr = (yf.download(tickers=Sname,period="1d",interval="1m").tail(1)).iloc[0,3]      
                    st.markdown("<h1 class='CurB'>Current Value : <span class='CurB_Am'>"+str(C_Pr)+"</span></h1>", unsafe_allow_html=True)
                    Qty = st.number_input("\nQuantity : ",min_value=1, max_value=getStockQty(C_User.uname,Sname), step=1)
                    st.markdown("\n")
                    if st.button("Sell"):
                        C_User.sellStock(Sname, Qty)
                        st.markdown("<div class='su'><p class='su_msg'>"+str(Qty)+" Of "+Sname +" Sold Successfully at price "+str(C_Pr)+"</p></div>", unsafe_allow_html=True)
            elif(opt == "Current Stocks"):
                df= C_User.getPortfolio()
                st.write(df)
                fig = px.pie(df, values='Investment Value', names='Stock')
                st.plotly_chart(fig, use_container_width=True)
            else:
                query="""select symbol,trans_time,price,action,volume,pl from transaction where username = %s and 1 = %s"""
                val= (C_User.uname,1)
                cur.execute(query,val)
                ls = cur.fetchall()
                d= {}
                sym,date,price,action,volume,pl = [],[],[],[],[],[]
                for i in ls:
                    sym.append(i[0])
                    date.append(i[1].strftime("%Y/%m/%d-%H:%M:%S"))
                    
                    price.append(float(i[2]))
                    action.append(str(i[3]))
                    volume.append(int(i[4]))
                    pl.append(float(i[5]))
                d['SYMBOL'] = sym
                d['PRICE'] = price
                d['ACTION'] = action
                d['VOLUME'] = volume
                d['PROFIT\LOSS'] = pl
                df = pd.DataFrame(d,index=date)
                st.write(df)
                # df.to_csv("Transaction_"+C_User.uname+".csv")
                st.download_button(label="Download",data=df.to_csv(),file_name="Transaction_"+C_User.uname+".csv")     
               
    if st.button("Log Out"):
        st.session_state['key'] = False