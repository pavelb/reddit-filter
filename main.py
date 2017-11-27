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

def loadSubscriptions(reddit):
    print('Loading subscriptions...')
    subscriptions = set(subName(s) for s in reddit.user.subreddits(limit=10000))
    addToRecent(subscriptions - set(loadRecentSubs('recent.txt').keys()))
    return subscriptions

def addToRecent(sub_names):
    recent = loadRecentSubs('recent.txt')
    for sub_name in sub_names:
        recent[sub_name] = int(time.time())
    saveRecentSubs(recent, 'recent.txt')

def dropFromRecent(sub_names):
    recent = loadRecentSubs('recent.txt')
    for sub_name in sub_names:
        recent.pop(sub_name, None)
    saveRecentSubs(recent, 'recent.txt')

def trimSubs(reddit):
    sub_names = set()
    for sub_name, timestamp in loadRecentSubs('recent.txt').items():
        if timestamp + 60 * 60 < time.time():
            sub_names.add(sub_name)
    if not sub_names:
        return
    print('Trimming  %s' % ', '.join('r/' + sub_name for sub_name in sub_names))
    dropFromRecent(sub_names)
    subs = [reddit.subreddit(sub_name) for sub_name in sub_names]
    for i in range(0, len(subs), 50):
        print('Sending batched unsubscribe request %d' % (1 + i // 50))
        subs[i].unsubscribe(subs[i + 1:i + 50])

def loadBlacklist(subscriptions):
    blacklist = loadSubreddits('unsub.txt') - subscriptions
    to_blacklist = set(loadRecentSubs('recent.txt').keys()) - subscriptions
    for sub_name in to_blacklist:
        print('Blacklist r/%s' % sub_name)
    blacklist |= to_blacklist
    saveSubreddits(blacklist, 'unsub.txt')
    dropFromRecent(blacklist)
    return blacklist

def tick(reddit):
    subscriptions = loadSubscriptions(reddit)
    blacklist = loadBlacklist(subscriptions)

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

    for i in range(0, len(to_hide), 50):
        print('Sending batched hide request %d' % (1 + i // 50))
        to_hide[i].hide(to_hide[i + 1:i + 50])
    for i in range(0, len(to_subscribe), 50):
        print('Sending batched subscribe request %d' % (1 + i // 50))
        to_subscribe[i].subscribe(to_subscribe[i + 1:i + 50])

    addToRecent(to_update)
    trimSubs(reddit)

def main(reddit):
    while True:
        try:
            tick(reddit)
        except:
            print('Ran into an error: %s' % sys.exc_info()[0])
        print('Sleeping...')
        time.sleep(60)
