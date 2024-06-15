from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import telebot
import json
import telebot
from telebot import types
from urllib.parse import urlparse
import configparser
import os
import schedule
from threading import Thread

#TODO вытянуть дебаг отдельно, а то че оно спамит епта

class Session:
    def __init__(self, Config, driver_executable_path="chromedriver.exe"):
        parsed_url = urlparse(Config["Queue"]["url"]) 
        
        #Внесение значений.
        self.url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
        self.host = parsed_url.scheme + "://" + parsed_url.netloc
        self.username = Config["Auth"]["username"]
        self.password = Config["Auth"]["password"]
        self.cookie = None
        self.queue = Config["Queue"]["url"]
        #Инициализация драйвера, настройка и тд. и тп.
        chrome_options = Options()
        #UPD Added chrome executable (not chromedriver)
        chrome_options.binary_location = f"{os.getcwd()}/Browser/chrome.exe"
        chrome_options.add_experimental_option("detach", True)
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        service = Service(executable_path=driver_executable_path)
        
        self.driver = webdriver.Chrome(service=service,options=chrome_options)
        #Загрузка кук из файла
        try:
            with open('cookies.json') as json_file:
                self.cookie = json.load(json_file)
        except:
            self.cookie = None

    def auth(self, timeout = 2):
        #Безопасный таймаут для прогрузки страницы (в целом не нужен)
        time.sleep(timeout)
        #Авторизация в OTRS
        self.driver.get(url=self.url) #URL выхода. (начальная страница) #Надо обработать это
        self.driver.find_element("id", "User").send_keys(self.username)
        self.driver.find_element("id", "Password").send_keys(self.password)
        self.driver.find_element("id", "LoginButton").click()
        #Безопасный таймаут для прогрузки страницы
        time.sleep(timeout)
        #Сохранение данных сессии
        self.cookie = self.driver.get_cookies()
        with open('cookies.json', 'w') as f:
            json.dump(self.cookie, f)
        print ("[$] Авторизация успешна, куки обновлены!")
        
            
    def validate_cookie(self):
        #Проверка возможно ли авторизироваться используя куки.
        self.driver.get(url=self.url)
        try:
            self.driver.add_cookie(self.cookie[0])
        except:
            pass
        self.driver.get(url=self.url)
        try:
            error_box = self.driver.find_element(by="class name", value="ErrorBox")
            if error_box:
                print("[!] Куки устарели, требуется повторная авторизация.")
                self.driver.delete_all_cookies()
                return False
        except:
            print("[$] Сессия актуальна!")
            return True

        
    def get_tickets(self):
        #Получает все тикеты очереди (ограничено страницей)
        self.driver.get(self.queue)
        soup = BeautifulSoup(self.driver.page_source, "lxml")
        TicketsFormData = soup.findAll("tr",class_ = "MasterAction")
        
#I HATE LIFE
        info = [
            [(element.get('title'), element.get('href'), element.text) if "MasterActionLink" in element.get('class', [])
                else (element.get('title'), element.get('href')) if element.name == 'a' 
                else element.get('title') 
                for element in action.find_all(['a', True]) 
                if (element.get('title') or element.get('href')) and
                   "UnreadArticles" not in element.get('class', []) and 
                   "UnreadArticles Small" not in element.get('class', [])] for action in TicketsFormData]
#I HATE LIFE
        
        #Приведение данных к удобному виду. 
        TicketsData = []
        for ticket in info:
            parsed_data = {"Link":self.host+ticket[3][1],
                           "Number":ticket[3][2],
                           "Title":ticket[6],
                           "Sender":ticket[5],
                           "Client":ticket[13]}
            TicketsData.append(parsed_data)
        return TicketsData

    def check_quenue_update(self,OldTickets):
        #print ("[DEB] Check queue update")
        NewTickets = self.get_tickets()
        NewTicketsNums = []
        NewTicketsList = []
        

        NewNumbers = []
        OldNumbers = []
        for newticket in NewTickets:
            NewNumbers.append(newticket["Number"])
        for oldticket in OldTickets:
            OldNumbers.append(oldticket["Number"])
         
        for number in NewNumbers:
            if number in OldNumbers:
                continue
            else:
                NewTicketsNums.append(number)
        
        
        
        if NewNumbers != OldNumbers: 
            #print ("[DEB] Check queue updated!")
            return OldTickets
        else:
            #print ("[DEB] Check queue NOT updated!")
            return NewTickets

    def check_tickets_updates(self,OldTickets):
        queue_updated = False
        NewTickets = self.get_tickets()
        NewTicketsNums = []
        NewTicketsList = []
        

        NewNumbers = []
        OldNumbers = []
        for newticket in NewTickets:
            NewNumbers.append(newticket["Number"])
        for oldticket in OldTickets:
            OldNumbers.append(oldticket["Number"])
         
        for number in NewNumbers:
            if number in OldNumbers:
                continue
            else:
                NewTicketsNums.append(number)
        #print(f"[DEB] NewNumbers: {NewNumbers}")
        #print(f"[DEB] OldNumbers: {OldNumbers}")
        #print(f"[DEB] NewTicketsNums: {NewTicketsNums}")
        
        
        if NewNumbers != OldNumbers:
            queue_updated = True
        
        for newticket in NewTickets:
            if newticket["Number"] in NewTicketsNums:
                NewTicketsList.append(newticket)
                #print("[DEB] Новый: ",end="")
                #print(newticket["Number"])
            #else:
                #print("[DEB] Старый: ",end="")
                #print(newticket["Number"])
        return NewTicketsList
                    
        
 
    


######################
#MAIN SHIT START HERE#
######################
def main(S, config):
    #Получение данных из конфига
    try:
        config.read("config.ini") 
    except Exception as Error:
        print (f"[!!!] Ошибка чтения конфиг файла.\n\n{str(Error)}")
        exit()

    #Старт telegram бота
    try:
        print("[$] Инициализация телеграмм сессии.")
        Telegram = telebot.TeleBot(config["Telegram"]["Bot_key"])
        Telegram.send_message(config["Telegram"]["Chat_id"],"Бот был запущен!")
    except Exception as Error:
        print(f"[!!!] Неудачно!\nПричина:{str(Error)}")
        exit()
    

    #Инициализация сессии и проверка авторизации
    #S = Session(config)
    if S.validate_cookie() == False:
        S.auth()
 
    #Просто приколямбус
    print(f"[$] Очередь: {S.queue}")
  
    #Получение изначальных тикетов и цикл работы
    Tickets = S.get_tickets()
    while True:
        print("[$] Поиск новых тикетов")
        Tickets = S.check_quenue_update(Tickets)
        Tickets_check = S.check_tickets_updates(Tickets)
        if len(Tickets_check) == 0:
            print("[$] Нет новых тикетов")
        else:
            print("[$] Найдены новые тикеты")
            Tickets = Tickets_check
            for Ticket in Tickets:
                TicketNum = Ticket["Number"]
                TicketTitle = Ticket["Title"]
                TicketSender = Ticket["Sender"]
                TicketClient = Ticket["Client"]
                TicketLink = Ticket["Link"]
                keyboard = types.InlineKeyboardMarkup()
                url_button = types.InlineKeyboardButton(text="Перейти к тикету ->", url=TicketLink)
                keyboard.add(url_button)
                Telegram.send_message(config["Telegram"]["Chat_id"],f"Новый тикет!\n\nНомер: {TicketNum}\nТема: {TicketTitle}\n\nОтправитель: {TicketSender}\nКлиент: {TicketClient}",reply_markup=keyboard)
        
        timeout = config["Other"]["Check_timeout"]
        print(f"[$] Переход в таймаут на {timeout} секунд...")
        time.sleep(int(timeout))
   
def schedulerSessionUpdater(S):
    if S.validate_cookie() == False:
        print("[$] При проверке оказалось что сессия устарела. ")
        S.auth()
        

def scheduler():
    schedule.every(3).hours.do(schedulerSessionUpdater, S)
    while True:
        print("[$] Ежедневная проверка сессии")
        schedule.run_pending()
        time.sleep(30)
  
config = configparser.ConfigParser() 
config.read("config.ini") 
S = Session(config)        

schedulerThread = Thread(target=scheduler) #нейминг
schedulerThread.start()
main(S, config)
