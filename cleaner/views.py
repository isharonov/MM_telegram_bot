import json
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from django.utils import timezone
from mmtelegrambot.settings import MM_CHAT_ID, WEBHOOK_SECRET_TOKEN
from .models import Message
from youtuber.utils import escape_str, send_api_request
from .utils import make_sim_search, make_result_message, save_result

def get_date_time_sent(update):
    date = update['message']['date']

    # Convert Unix timestamp to naive datetime in UTC
    time_sent = datetime.utcfromtimestamp(date)

    # Make the datetime aware in the local timezone
    time_sent = timezone.make_aware(time_sent)

    return time_sent

def handle_search_command(update):
    user_id = update['message']['from']['id']
    chat_id = update['message']['chat']['id']
    sent_at = get_date_time_sent(update)
    message_id = update['message']['message_id']
    text = update['message'].get('text')
    question = text.replace('/search', '').strip()
    try:
        result = make_sim_search(question)
        save_result(message_id, user_id, chat_id, sent_at, question, result)
        message = make_result_message(result)
        send_api_request("sendMessage", {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'MarkdownV2',
            'disable_notification': True,
            'disable_web_page_preview': True,
            'reply_to_message_id': message_id
        })
    except Exception as e:
        print(e)
        return HttpResponseBadRequest('Bad Request')

@csrf_exempt
def telegram_bot(request):
    if request.method == 'POST':
        secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret_token == WEBHOOK_SECRET_TOKEN:
            update = json.loads(request.body.decode('utf-8'))
            if 'message' in update:
                chat_id = update['message']['chat']['id']
                message_id = update['message']['message_id']

                if str(chat_id) == MM_CHAT_ID:
                    if 'new_chat_member' in update['message']:
                        is_deleted = send_api_request('deleteMessage', {
                            'chat_id': chat_id,
                            'message_id': message_id
                        })
                        if is_deleted:
                            first_name = update['message']['new_chat_member'].get('first_name')
                            username = update['message']['new_chat_member'].get('username')
                            name = first_name if first_name is not None else username
                            name = escape_str(name)

                            msg_new = send_api_request('sendMessage', {
                                'chat_id': chat_id,
                                'text': f'Приветствуем нового участника _{name}_ 👋',
                                'parse_mode': 'MarkdownV2'
                            })

                            response = msg_new.json()
                            if response['ok']:
                                message_id = response['result']['message_id']
                                text = response['result']['text']

                                message = Message(
                                    message_id=message_id,
                                    text=text
                                )

                                try:
                                    message.save()
                                    return HttpResponse('ok')
                                except:
                                    return HttpResponseBadRequest('Bad Request')
                    elif 'pinned_message' in update['message']:
                        pinned_message_id = update['message']['pinned_message']['message_id']
                        try:
                            message = Message.objects.get(message_id=pinned_message_id)
                            message.skip = True
                            message.save()
                        except Exception as e:
                            print(f'Error while skipping pinned message {message_id}:\n {e}')
                    elif '/search' in update['message'].get('text'):
                        handle_search_command(update)
                    else:
                        user_id = update['message']['from']['id']
                        text = update['message'].get('text')
                        time_sent = get_date_time_sent(update)

                        message = Message(
                            message_id=message_id,
                            user_id=user_id,
                            time_sent=time_sent,
                            text=text
                        )

                        try:
                            message.save()
                            return HttpResponse('ok')
                        except:
                            return HttpResponseBadRequest('Bad Request')
                elif update['message']['chat']['type'] == 'private':
                    if '/start' in update['message'].get('text'):
                        pass
                    elif '/search' in update['message'].get('text'):
                        handle_search_command(update)
            return HttpResponse('ok')
        else:
            return HttpResponseBadRequest('Bad Request')
    else:
        return HttpResponseBadRequest('Bad Request')

