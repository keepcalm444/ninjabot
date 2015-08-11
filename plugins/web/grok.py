"""
Polls the grok forums for new posts
"""
from dateutil.parser import parse as parse_date
import requests
import re

DISCOURSE_FORUM_BASE = 'https://forum.groklearning.com'

class Plugin(object):
    def load(self, bot, config):
        self.bot = bot
        self.cookieString = 'grok_session=' + config['ck_session'] + '; _t=' + config['ck_t'] + '; grok_discourse=' + config['ck_discourse']
        self.notifyChan = config['notify_chan']
        self.ignoreThreads = config['ignore_threads']
        self.catRegexp = config['category_regexp']
        self.categoryIDs = []
        self.categoryNames = {}
        self.seenPosts = {}
        self.loaded = False
        print(config)
        self._loadCategories()
        self._resetSeenPosts()

    def _getHeaders(self):
        return {
                'cookie': self.cookieString,
                'user-agent': 'ninjabot web.grok (like Gecko; rv:1.0) AppleWebKit/367.5 Gecko/20100101 Firefox/41.0'
        }

    def _loadCategories(self):
        global DISCOURSE_FORUM_BASE
        r = requests.get(DISCOURSE_FORUM_BASE + '/categories.json', headers=self._getHeaders())
        obj = r.json()['category_list']
        for cat in obj['categories']:
            if re.search(self.catRegexp, cat['slug']):
                self.categoryIDs.append(cat['id'])
                self.categoryNames[cat['id']] = cat['name']
                print("Found cat id",cat['id'],"-",cat['name'])

    def _forEachLatestPost(self, during, after=lambda: False):
        global DISCOURSE_FORUM_BASE
        r = requests.get(DISCOURSE_FORUM_BASE + '/latest.json', headers=self._getHeaders())
        obj = r.json()
        for topic in obj['topic_list']['topics']:
            during(topic)
        after()

    def _getPostUUID(self, post):
        return post['last_posted_at'] + '$' + str(post['id'])

    # so there isn't a huge spam of 'new' posts on bot startup.
    def _resetSeenPosts(self):
        self._forEachLatestPost(lambda post: self.seenPosts.update({self._getPostUUID(post): True}))
        print("*** SEEN POSTS ***")
        print(self.seenPosts)
        self.loaded = True

    def getPostMsg(self,json):
        is_new = json['posts_count'] == 1
        time = parse_date(json['created_at'] if is_new else json['last_posted_at'])
        print(time)
        user = json['last_poster_username'][0] + '\u200D' + json['last_poster_username'][1:]
        url = 'https://forum.groklearning.com/t/-/{0}/{1}'.format(json['id'], json['posts_count'])
        viewDesc = str(json['views']) + ' view' + ('s' if json['views'] != 1 else '')
        likeDesc = str(json['like_count']) + ' like' + ('s' if json['like_count'] != 1 else '')
        postDesc = str(json['posts_count']) + ' post' + ('s' if json['posts_count'] != 1 else '')
        res = "'\x02{title}\x0F' in {cat} at \x02{time}\x0F. {posts}, most recent by @\x02{user}\x0F. {likes}, {views}. \x02{url}\x0F"
        if is_new:
            res = "'\x02{title}\x0F' in {cat} at \x02{time}\x0F by @\x02{user}\x0F. {views}. \x02{url}\x0F"
        return res.format(
                    title=json['title'],
                    cat=self.categoryNames[json['category_id']],
                    time=time.strftime('%a, %I:%M:%S %p'),
                    posts=postDesc,
                    user=user,
                    likes=likeDesc,
                    views=viewDesc,
                    url=url
                )

    def trigger_grokpoll(self, msg):
        "Force a poll of the grok forum"
        self.timer_60()
        self.bot.privmsg(msg.channel, "Polled")

    def timer_60(self):
        if not self.loaded: return
        print("Polling...")
        def _onPost(json):
            if json['category_id'] not in self.categoryIDs: return
            if json['id'] in self.ignoreThreads: return
            if self._getPostUUID(json) in self.seenPosts: return
            self.seenPosts[self._getPostUUID(json)] = True
            if json['posts_count'] == 1:
                self.bot.privmsg(self.notifyChan, "New forum topic! {0}".format(self.getPostMsg(json)))
            else:
                self.bot.privmsg(self.notifyChan, "New forum post in {0}".format(self.getPostMsg(json)))

        self._forEachLatestPost(_onPost)
        print("Done.")


