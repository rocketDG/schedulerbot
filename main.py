import requests
import redis
import os
import json
import sys
from time import sleep


# # TODO:

"""

1) Мне нужно проверить, что человек присоединился, чтобы отправлять другие команды
2) Нужно разобраться с тем как будет учитываться статистика выполнения заданий
3) Понять как определять очередь для жителей комнаты
4) Нужно сделать уведомления о том, чья очередь выполнять задание
5) Нормально выводить все команды (по красивше ты шо лиса)
6) Айнура жепа

"""



# BOT
class Bot:

    def __init__(self, token):
        self.token = token
        self.MAIN_URL = f'https://api.telegram.org/bot{token}/'
        self.client = redis.Redis(host = '192.168.100.8', port = 6379)


    # Get updates from API
    def get_updates(self, offset = None, timeout = 30):
        params = {'timeout': timeout, 'offset': offset}
        responce = requests.get(self.MAIN_URL + 'getUpdates', params)
        result_json = responce.json()['result']
        return result_json

    # send message to the chat
    def send_message(self, chat_id, text):
        params = {'chat_id': chat_id, 'text':text}
        response = requests.post(self.MAIN_URL + 'sendMessage', params)
        return response


    def get_last_update(self):

        result = self.get_updates()

        if len(result) > 0:
            last_update = result[-1]
        else:
            last_update = result[len(result)]

        return last_update

    # function that will called in the very beginning
    def start(self):
        msg = "Welcome to Div&Do bot, here you can track whose is it turn to do particular task!"
        self.send_message(self.get_last_update()['message']['chat']['id'], msg)

    # function that will join the user to the participants
    #TODO:
    # Нужно реализовать хранение информации в редис
    # решить как хранить юзеров когда они присоединяться
    def join(self):
        chat_id = self.get_last_update()['message']['chat']['id']
        allias = self.get_last_update()['message']['from']['username']
        user_id = self.get_last_update()['message']['from']['id']

        if self.client.hexists(chat_id, allias):
            self.send_message(chat_id, 'You are already joined!')
        else:
            # setting statistics for tasks
            # TODO: when we add new task we need update list of tasks for every user
            set = self.client.smembers('tasks' + str(chat_id))

            while len(set) != 0:
                task_pair = set.pop()
                # adding task and number of times it was done by user in the hash table
                self.client.hset(allias+str(chat_id), task_pair, 0)

            # PREV VERSION:
            # self.client.hset(chat_id, allias, user_id)
            # self.send_message(chat_id, self.client.hget(chat_id, allias))

            # NEW VERSION
            # adding user to the 'list' of joined users
            self.client.hset(chat_id, allias, allias+str(chat_id))

            set = self.client.smembers('tasks' + str(chat_id))
            while len(set) != 0:
                self.client.rpush(set.pop().decode('utf-8') + str(chat_id) + 'queue', allias)
            self.send_message(chat_id, 'Nice. Now you can use other commands!')

    # function that checks if user is joined
    def is_join(self, chat_id, allias):

        if self.client.hexists(chat_id, allias):
            return True
        else:
            return False

    # add new task
    def add_task(self):
        chat_id = self.get_last_update()['message']['chat']['id']
        allias = self.get_last_update()['message']['from']['username']
        task = self.get_last_update()['message']['text'].split(' ', 1)

        # user can use other commands only when he(she and other great genders also should be joined) is joined
        if self.is_join(chat_id, allias):

            if len(task) > 1 and not self.client.sismember('tasks' + str(chat_id), task[1]):
                # GOVNO CODE MODE: ON
                self.client.sadd('tasks' + str(chat_id), task[1])

                # adding new task and its counter
                # 1st arg - name of hash, 2nd arg - task, 3rd - counter
                # self.client.hset(allias+str(chat_id), task[1], 0)

                usernames = self.client.hgetall(chat_id)        # hash that contains all usernames and titles of list with tasks

                for i in usernames:
                    self.client.hset(usernames[i], task[1], 0)

                # generating queue for task
                # self.queue_generation(task[1], chat_id)

                # debug god
                self.send_message(chat_id, self.client.hexists(allias+str(chat_id), task[1]))
            elif len(task) > 1 and self.client.sismember('tasks' + str(chat_id), task[1]):
                self.send_message(chat_id, 'There is already such task!')
            else:
                self.send_message(chat_id, 'You should specify task!')
        else:
            self.send_message(chat_id, 'You should joined to use commands. Use /join to use other commands')

    # show all tasks
    def show_tasks(self):
        chat_id = self.get_last_update()['message']['chat']['id']
        allias = self.get_last_update()['message']['from']['username']

        if self.is_join(chat_id, allias):

            hash = self.client. hgetall(allias + str(chat_id))
            msg = 'Tasks statistics of @{}: \n'.format(allias)

            if self.client.scard('tasks' + str(chat_id)) == 0:
                self.send_message(chat_id, 'There are no tasks! Add tasks!')
            else:
                for i in hash:
                    msg = msg + i.decode('utf-8') + ': ' + hash[i].decode('utf-8') + '\n'

                self.send_message(chat_id, msg)
        else:
            self.send_message(chat_id, 'You should joined to use commands. Use /join to use other commands')



    def find_turn(self, chat_id, message):
        hash = self.client.hgetall(chat_id)

        min = sys.maxsize
        allias = ""

        if len(hash) > 0:
            for i in hash:
                current_bytes = self.client.hget(i.decode('utf-8')+str(chat_id), message)
                current = int.from_bytes(current_bytes, "big")
                if current < min:
                    min = current
                    allias = i

            self.send_message(chat_id, "Now it is turn of @{} to do {}!".format(allias.decode('utf-8'), message))

        else:
            self.send_message(chat_id, "There is no users!")


    def complete_task(self):
        # get the task from message of user
        # increase the counter

        chat_id = self.get_last_update()['message']['chat']['id']
        allias = self.get_last_update()['message']['from']['username']

        if self.is_join(chat_id, allias):
            message = self.get_last_update()['message']['text'].split(' ', 1)
            if len(message) > 1 and self.client.sismember('tasks' + str(chat_id), message[1]):
                #counter_str = self.client.hget(allias + str(chat_id), message[1])
                #counter = int(counter_str)

                self.client.hincrby(allias + str(chat_id), message[1], 1)

                #self.client.incr(message[1] + str(chat_id) + 'counter')
                #counter = int(self.client.get(message[1] + str(chat_id) + 'counter').decode('utf-8'))

                #if counter == self.client.llen(message[1] + str(chat_id) + 'queue'):
                #    self.client.set(message[1] + str(chat_id) + 'counter', 0)

                self.send_message(chat_id, 'Great job')
                self.show_tasks()
            elif len(message) > 1 and not self.client.sismember('tasks' + str(chat_id), message[1]):
                self.send_message(chat_id, 'There is no such task!')
            else:
                self.send_message(chat_id, 'Specify which task you completed?')
        else:
            self.send_message(chat_id, 'You should joined to use commands. Use /join to use other commands')

    # Теперь очередь будет генирироваться нормально
    # Заводим коунтер для каждого юзера
    # После выполнения задания коунтер инкрементиться
    # В функции whose_next просто нходится первый элемент с меньшим каунтером

    def whose_next(self):
        chat_id = self.get_last_update()['message']['chat']['id']
        allias = self.get_last_update()['message']['from']['username']

        if self.is_join(chat_id, allias):
            message = self.get_last_update()['message']['text'].split(' ', 1)

            if len(message) > 1 and self.client.sismember('tasks' + str(chat_id), message[1]):

            #    counter = int(self.client.get(message[1] + str(chat_id) + 'counter').decode('utf-8'))
            #    allias_turn = self.client.lindex(message[1] + str(chat_id) + 'queue', counter).decode('utf-8')
            #    self.send_message(chat_id, 'The turn of @{}'.format(allias_turn))


                self.find_turn(chat_id, message[1])

            elif len(message) > 1 and not self.client.sismember('tasks' + str(chat_id), message[1]):
                self.send_message(chat_id, 'There is no such task for this chat!')
            else:
                self.send_message(chat_id, 'Specify for which task!')

        else:
            self.send_message(chat_id, 'You should joined to use commands. Use /join to use other commands')


    #def queue_generation(self, task, chat_id):
        # simple implementation
        #set = self.client.smembers('tasks' + str(chat_id))


        #hash = self.client.hgetall(chat_id)
        #self.client.append(task + str(chat_id) + 'counter', 0) # counter
        #for i in hash:
            #self.client.rpush(task + str(chat_id) + 'queue', i)



def main():
    token = '705269726:AAHaqEh0Wa4SRcjxyDLYEYMwc7d_eJ4F9O4'
    my_bot = Bot(token)

    with open('updates.json', 'w') as write_file:
        json.dump(my_bot.get_updates(), write_file)

    last_update = my_bot.get_last_update()
    last_update_id = last_update['update_id']

    while True:
        upd = my_bot.get_last_update()
        upd_command = upd['message']['text']
        if last_update_id == upd['update_id']:
            if '/start' in upd_command:
                my_bot.start()
                last_update_id+=1
            elif '/join' in upd_command:
                my_bot.join()
                last_update_id+=1
            elif '/addtask' in upd_command:
                my_bot.add_task()
                last_update_id+=1
            elif '/showtasks' in upd_command:
                my_bot.show_tasks()
                last_update_id+=1
            elif '/complete' in upd_command:
                my_bot.complete_task()
                last_update_id+=1
            elif '/who_next' in upd_command:
                my_bot.whose_next()
                last_update_id+=1
            else:
                last_update_id+=1

if __name__ == '__main__':
    main()
