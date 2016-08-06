from collections import defaultdict


class Event:
    def __init__(self, key, data):
        self.key = key
        self.data = data


class Observer:
    def __init__(self):
        self.subscribers = defaultdict(list)

    def subscribe(self, key, callback):
        '''Subscribe to the event named `key`. When it happens
        call `callback` with one argument, the event.'''
        self.subscribers[key].append(callback)

    def unsubscribe(self, key, callback):
        '''Unsubscribe `callback` from the event named `key`'''
        self.subscribers[key].remove(callback)

    def notify(self, key, data):
        '''Notify every subscriber that the event named `key` has
        been fired. `data` will be available as the property "data"
        of the event'''
        for cb in self.subscribers[key]:
            cb(Event(key=key, data=data))
