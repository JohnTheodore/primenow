import io
import ipdb
import json
import re
import requests
import sys
import time
from bs4 import BeautifulSoup
from pycookiecheat import chrome_cookies
from pygame import mixer


primenow_url = 'https://primenow.amazon.com'
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) \
    Chrome/80.0.3987.149 Safari/537.36',
}


def get_primenow_cookies():
  return chrome_cookies(primenow_url)


def query_primenow(url, cookies, method='get', data=None, params=None):
  if method == 'get':
    response = requests.get(url, headers=headers, cookies=cookies)
  elif method == 'post':
    response = requests.post(url, headers=headers, cookies=cookies, params=params, data=data)
  response.raise_for_status()
  if 'Sign in' in str(response.content):
    sys.exit('Invalid authentication.')
  return response


def exit_on_empty_shopping_cart(checkout_button_html):
  if len(checkout_button_html) < 1:
    sys.exit('Shopping cart is currently empty.')


def get_checkout_html():
  primenow_cookies = get_primenow_cookies()
  shopping_cart_response = query_primenow('https://primenow.amazon.com/cart', primenow_cookies)
  primenow_cookies.update(shopping_cart_response.cookies.get_dict())
  shopping_cart_html = BeautifulSoup(shopping_cart_response.content, features='html.parser')
  checkout_button_html = shopping_cart_html.findAll('span', {'class': 'cart-checkout-button'})
  exit_on_empty_shopping_cart(checkout_button_html)
  checkout_link = checkout_button_html[0].find('a')['href']
  checkout_url = '%s%s' % (primenow_url, checkout_link)
  checkout_response = query_primenow(checkout_url, primenow_cookies)
  primenow_cookies.update(checkout_response.cookies.get_dict())
  return (BeautifulSoup(checkout_response.content, features='html.parser'), primenow_cookies)


def get_earliest_delivery_window(checkout_html):
  two_hour_soup_block = checkout_html.findAll('div', {'id': 'two-hour-window'})
  if len(two_hour_soup_block) < 1:
    print('empty delivery box div again?')
    buy_primenow_groceries()
  two_hour_soup_block = two_hour_soup_block[0]
  delivery_times = two_hour_soup_block.findAll('div', {'class': 'a-section a-spacing-none'})
  available_delivery_windows = []
  for delivery_time in delivery_times:
    time_slot = delivery_time.findAll(text=re.compile(' PM'))[0].strip()
    delivery_key_html = delivery_time.find(attrs={'data-action': 'selectdeliverywindow'})['data-selectdeliverywindow']
    delivery_json = json.loads(delivery_key_html)
    available_delivery_windows.append({'time_slot': time_slot, 'delivery_json': delivery_json})
  print(available_delivery_windows)
  return available_delivery_windows[0]


def set_earliest_delivery_window(checkout_html, delivery_window, primenow_cookies):
  next_url = checkout_html.findAll('form', {'action' : re.compile('/checkout/deliveryslot/')})[0]['action'].split('&')[0]
  delivery_slot_form = checkout_html.findAll('form', {'name' : 'deliverySlotForm'})[0]
  token_value = delivery_slot_form.findAll('input', {'name': 'tokenValue'})[0]['value']
  params = (
      ('nexturl', next_url),
      ('ref_', 'pn_co_ds_c'),
      ('fromPanel', 'delivery-slot'),
  )
  data = delivery_window['delivery_json']
  data.update({
    'tokenName': 'delivery-slot',
    'shipOptionType': 'scheduled_two_hour_delivery',
    'sameDay': '',
    'deliveryType': 'UNATTENDED'}
  )
  data['tokenValue'] = token_value
  checkout_prefetch_url = 'https://primenow.amazon.com/checkout/prefetch'
  response = query_primenow(checkout_prefetch_url, primenow_cookies, method='post', params=params, data=data)
  return response


def continue_to_latest_delivery(set_delivery_window_response):
  ipdb.set_trace()
  return True


def checkout(checkout_html, primenow_cookies):
  delivery_window = get_earliest_delivery_window(checkout_html)
  set_delivery_window_response = set_earliest_delivery_window(checkout_html, delivery_window, primenow_cookies)
  continue_to_delivery_response = continue_to_latest_delivery(set_delivery_window_response)
  data = {
    'events': [
      {
        'data': {
          'renderedToMeaningful': 151,
          'renderedToViewed': 151,
          'renderedToImpressed': 1152,
          'schemaId': 'csa.PageImpressed.2',
          'timestamp': '2020-04-04T21:10:05.564Z',
          'messageId': '4fsntm-rgsmgi-vdaomx-vnm3p9',
          'application': 'Retail',
          'obfuscatedMarketplaceId': 'A1IXFGJ6ITL7J4',
          'producerId': 'csa',
          'entities': {
            'page': {
              'id': '5q6w1b-xtakwu-ip6i05-bnvcv4',
              'requestId': '32291AP8WS13QAPZYMAA',
              'meaningful': 'interactive',
              'url': 'https://primenow.amazon.com/checkout/enter-checkout?merchantId=A23L00C7H3DINE&ref=pn_sc_ptc_bwr',
              'server': 'primenow.amazon.com',
              'path': '/checkout/enter-checkout',
              'referrer': 'https://primenow.amazon.com/cart?ref_=pn_gw_nav_cart',
              'title': 'Amazon Prime Now: Checkout',
              'pageType': 'CheckoutDeliverySlotDesktopWeb',
              'subPageType': 'cart-to-deliverySlot',
              'pageTypeId': ''
            },
            'session': {
              'id': '144-7656386-8014611'
            }
          }
        }
      }
    ]
  }
  return True


def is_delivery_time_available(checkout_html):
  no_delivery_time = checkout_html.findAll(text=re.compile('No delivery windows available.'))
  if len(no_delivery_time) > 0:
    return False
  wants_address_selected = checkout_html.findAll(text=re.compile('Select Delivery Address'))
  if len(wants_address_selected) > 0:
    print('dumb address bug')
    return False
  return True


def play_victory_music():
  daft_punk = requests.get('https://download.mp3-here.icu/i/Daft-Punk-End-Of-Line.mp3')
  mixer.init()
  mixer.music.load(io.BytesIO(daft_punk.content))
  mixer.music.play()


def buy_primenow_groceries():
  while True:
    checkout_html = get_checkout_html()
    delivery_time_available = is_delivery_time_available(checkout_html[0])
    if delivery_time_available:
      play_victory_music()
      time.sleep(3)
      checkout(checkout_html[0], checkout_html[1])
      sys.exit('Finished checkout out.')
    print('Still no delivery times available. :(')
    time.sleep(30)
