import sqlite3, os, configparser, requests, socket, smtplib, ssl, time, logging, re
from flask import Flask, request
from threading import Timer, Thread

app = Flask(__name__)

db_file = "notice.db"
logging.basicConfig(filename="app.log", format = u'%(asctime)s  %(filename)s[LINE:%(lineno)d]# %(levelname)s %(message)s', level=logging.INFO)
logging.info("Program started")

config = configparser.ConfigParser()
config.read("settings.ini")
smtp_server  = config.get("Settings", "smtp_server")
port         = config.get("Settings", "port")
sender_email = config.get("Settings", "sender_email")
sender_title = config.get("Settings", "sender_title")
password     = config.get("Settings", "password")
interval     = int(config.get("Settings", "interval"))
apikey       = config.get("Settings", "apikey")

def create_db():
    logging.info("Creating DB")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE "notice" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        "ticker" TEXT NOT NULL,
        "email" TEXT NOT NULL,
        "max_price" REAL,
        "min_price" REAL,
        "max_is_sent" INTEGER DEFAULT 0,
        "min_is_sent" INTEGER DEFAULT 0
        );
        """)
    conn.close()

@app.route('/subscription', methods=['POST'])
def add_subscription():
    try:
        data = request.get_json()
    except:
        logging.error("JSON Decoding error")
        return "JSON Decoding error"
    if not 'email' in data:
        logging.error("Email is required parameter")
        return "Email is required parameter"
    if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        logging.error("Email is not valid")
        return "Email is not valid"
    if not 'ticker' in data:
        logging.error("Ticker is required parameter")
        return "Ticker is required parameter"
    if (not 'max_price' in data) and (not 'min_price' in data):
        logging.error("One of max_price or min_price parameter is required")
        return "One of max_price or min_price parameter is required"
    if 'max_price' in data:
        try:
            float(data['max_price'])
        except ValueError:
            logging.error("Max_price is not valid price")
            return "Max_price is not valid price"
    else:
        data["max_price"] = None
    if 'min_price' in data:
        try:
            float(data['min_price'])
        except ValueError:
            logging.error("Min_price is not valid price")
            return "Min_price is not valid price"
    else:
        data["min_price"] = None

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT count(*) FROM notice WHERE email=? AND ticker=?", (data["email"], data["ticker"]))
    result=cursor.fetchone()
    if result[0] > 0:
        conn.close()
        logging.info("You are already subscribed on this ticker")
        return "You are already subscribed on this ticker"

    cursor.execute("SELECT count(*) FROM notice WHERE email=?", (data["email"],))
    result=cursor.fetchone()
    if result[0] >= 5:
        conn.close()
        logging.info("To many ticker for one email")
        return "To many tickers for one email"

    cursor.execute("""
        INSERT INTO notice (ticker, email, max_price, min_price)
        VALUES (:ticker, :email, :max_price, :min_price)
        """, 
        data
        )
    conn.commit()
    conn.close()
    logging.info("Success subscription")
    return "Success subscription"

@app.route('/subscription', methods=['DELETE'])
def del_subscription():
    email = request.args.get('email')
    ticker = request.args.get('ticker')
    if isinstance(email, type(None)): 
        logging.error("DELETE format error")
        return "DELETE format error"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    if isinstance(ticker, type(None)):
        cursor.execute("DELETE FROM notice WHERE email=?", (email,))
    else:
        cursor.execute("DELETE FROM notice WHERE email=? AND ticker=?", (email, ticker))
    conn.commit()
    conn.close()
    logging.info("Subscription deleted")
    return "Subscription deleted"    

def get_price(ticker):
    url = "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol="+ticker+"&apikey="+apikey
    result = requests.get(url)
    dataobj = result.json()
    if 'Note' in dataobj:
        logging.warning(dataobj['Note'])
        return False
    return dataobj['Global Quote']['05. price']

def send_email (email, title, msg):
    message = 'From: {}<{}>\nTo: {}\nSubject: {}\n\n{}'.format(sender_title, sender_email, email, title, msg)
    context = ssl.create_default_context()
    try:
        server = smtplib.SMTP(smtp_server, port, timeout=5)
        server.starttls(context=context)
        server.login(sender_email, password)
        server.sendmail(sender_email, email, message)
        server.quit()
        logging.info("Email for " + email + " is sent")
        return True
    except smtplib.SMTPAuthenticationError as err:
        logging.error(err)
        return False
    except (TimeoutError, socket.timeout):
        logging.error("SMTP Server Timeout Error")
        return False
    return False

class Scheduler(object):
    def __init__(self, sleep_time, function):
        self.sleep_time = sleep_time
        self.function = function
        self._t = None

    def start(self):
        if self._t is None:
            self._t = Timer(self.sleep_time, self._run)
            self._t.start()
        else:
            raise Exception("this timer is already running")

    def _run(self):
        self.function()
        self._t = Timer(self.sleep_time, self._run)
        self._t.start()

    def stop(self):
        if self._t is not None:
            self._t.cancel()
            self._t = None

def check_price():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT ticker FROM notice WHERE max_is_sent=0 OR min_is_sent=0")
    tickers=cursor.fetchall()

    for ticker in tickers:
        cur_price = get_price(ticker[0])
        if cur_price:
            cursor.execute("SELECT * FROM notice WHERE ticker=? AND (max_is_sent=0 OR min_is_sent=0)",(ticker[0],))
            subsc=cursor.fetchall()
            for row in subsc:
                id          = row[0]
                email       = row[2]
                max_price   = row[3]
                min_price   = row[4]
                max_is_sent = row[5]
                min_is_sent = row[6]

                if not isinstance(max_price, type(None)):
                    if float(cur_price) >= max_price and not max_is_sent:
                        title = 'Price is higher'
                        msg = ticker[0] + ' price is higher then ' + str(max_price) + '\nCurrent price: ' + cur_price
                        if send_email(email, title, msg):
                            cursor.execute("UPDATE notice SET max_is_sent=1 WHERE id=?",(str(id),))
                            conn.commit()
                if not isinstance(min_price, type(None)):
                    if float(cur_price) <= min_price and not min_is_sent:
                        title = 'Price is lower'
                        msg = ticker[0] + ' price is lower then ' + str(min_price) + '\nCurrent price: ' + cur_price
                        if send_email(email, title, msg):    
                            cursor.execute("UPDATE notice SET min_is_sent=1 WHERE id=?",(str(id),))
                            conn.commit()
    conn.close()

if __name__ == '__main__':
    if not os.path.isfile(db_file):
        create_db()
    scheduler = Scheduler(interval, check_price)
    scheduler.start()
    print ('Monitoring is on duty')
    app.run()
    scheduler.stop()
