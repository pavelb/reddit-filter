import praw
import time
import sys

def loadRecentSubs(filename):
    recent = {}
    with open(filename, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if line:
                sub_name, timestamp = line.split(' ')
                recent[sub_name] = int(timestamp)
    return recent

def saveRecentSubs(recent, filename):
    with open(filename, 'w') as f:
        for sub_name, timestamp in sorted(recent.items()):
            f.write('%s %d\n' % (sub_name, timestamp))

def loadSubreddits(filename):
    with open(filename, 'r') as f:
        return set(line.strip() for line in f.readlines())

def saveSubreddits(subreddits, filename):
    with open(filename, 'w') as f:
        for sub in sorted(list(subreddits)):
            f.write('%s\n' % sub)

def subName(sub):
    return sub.display_name.lower()

def loadSubscriptions(reddit, recent_file):
    print('Loading subscriptions...')
    subscriptions = set(subName(s) for s in reddit.user.subreddits(limit=10000))
    addToRecent(subscriptions - set(loadRecentSubs(recent_file).keys()))
    return subscriptions

def addToRecent(sub_names, recent_file):
    recent = loadRecentSubs(recent_file)
    for sub_name in sub_names:
        recent[sub_name] = int(time.time())
    saveRecentSubs(recent, recent_file)

def dropFromRecent(sub_names, recent_file):
    recent = loadRecentSubs(recent_file)
    for sub_name in sub_names:
        recent.pop(sub_name, None)
    saveRecentSubs(recent, recent_file)

def batch(operation, items, size=50):
    items = list(items)
    for i in range(0, len(it), size):
        print('Sending batched %s request %d' % (operation, 1 + i // size))
        getattr(items[i], operation)(items[i + 1:i + size])

def trimSubs(reddit, recent_file):
    sub_names = set()
    for sub_name, timestamp in loadRecentSubs(recent_file).items():
        if timestamp + 60 * 60 < time.time():
            sub_names.add(sub_name)
    if not sub_names:
        return
    print('Trimming  %s' % ', '.join('r/' + sub_name for sub_name in sub_names))
    dropFromRecent(sub_names, recent_file)
    batch('unsubscribe', reddit.subreddit(sub_name) for sub_name in sub_names)

def loadBlacklist(blacklist_file, recent_file, subscriptions):
    blacklist = loadSubreddits(blacklist_file) - subscriptions
    to_blacklist = set(loadRecentSubs(recent_file).keys()) - subscriptions
    for sub_name in to_blacklist:
        print('Blacklist r/%s' % sub_name)
    blacklist |= to_blacklist
    saveSubreddits(blacklist, blacklist_file)
    dropFromRecent(blacklist, recent_file)
    return blacklist

def tick(reddit, recent_file, blacklist_file):
    subscriptions = loadSubscriptions(reddit, recent_file)
    blacklist = loadBlacklist(blacklist_file, recent_file, subscriptions)

    to_update = []
    to_hide = []
    to_subscribe = []

    print('Loading front page...')
    for submission in reddit.subreddit('all').hot(limit=1000):
        sub_name = subName(submission.subreddit)
        if sub_name in subscriptions:
            // print('Allowing  r/%-30s %s' % (sub_name, submission.title[:100]))
            to_update.append(sub_name)
        elif sub_name in blacklist:
            print('Hiding    r/%-30s %s' % (sub_name, submission.title[:100]))
            to_hide.append(submission)
        else:
            print('Subbing   r/%-30s %s' % (sub_name, submission.title[:100]))
            to_update.append(sub_name)
            to_subscribe.append(submission.subreddit)

    batch('hide', to_hide)
    batch('subscribe', to_subscribe)
    addToRecent(to_update, recent_file)
    trimSubs(reddit)

def main(reddit, recent_file='recent.txt', blacklist_file='unsub.txt'):
    while True:
        try:
            tick(reddit, recent_file, blacklist_file)
        except:
            print('Ran into an error: %s' % sys.exc_info()[0])
        print('Sleeping...')
        time.sleep(60)
