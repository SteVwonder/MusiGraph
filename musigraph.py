import requests
import json
import argparse
from hashlib import md5
import networkx as nx
import pygraphviz as pgv
import matplotlib.pyplot as plt

API_ROOT = "http://ws.audioscrobbler.com/2.0/"

class ConfigException(Exception):
    pass

class APIException(Exception):
    pass

def parse_config(config_path):
    with open(config_path, 'r') as json_file:
        config = json.loads(json_file.read())
        if 'lastfm' not in config:
            raise ConfigException('lastfm not in config')
        return config

def save_config(config_path, config_dict):
    with open(config_path, 'w') as json_file:
        json_dump = json.dumps(config_dict, sort_keys=True, indent=4, separators=(',', ': '))
        json_file.write(json_dump)

class LastFm:
    def __init__(self, config_path):
        config = parse_config(config_path)
        lastfm_config = config['lastfm']
        if 'api_key' not in lastfm_config:
            raise ConfigException('api_key not in lastfm_config')
        if 'secret' not in lastfm_config:
            raise ConfigException('secret not in lastfm_config')
        if 'session_key' not in lastfm_config:
            lastfm_config['session_key'] = ""
        for key in lastfm_config:
            setattr(self, key, lastfm_config[key])
        if self.session_key == "":
            session = self.get_session()
            self.session_key = session['key']
            self.username = session['name']
            lastfm_config['session_key'] = self.session_key
            lastfm_config['username'] = self.username
        save_config(config_path, config)

    def build_signature(self, param_tuples):
        param_tuples.sort(key=lambda tup: tup[0])
        sig_str = []
        for tup in param_tuples:
            sig_str.append(str(tup[0]).encode('utf-8'))
            sig_str.append(str(tup[1]).encode('utf-8'))
        sig_str.append(str(self.secret).encode('utf-8'))
        sig_str = "".join(sig_str)
        return md5(sig_str).hexdigest()

    def get(self, method, signature=False, **kwargs):
        params = {}
        params['method'] = method
        params['api_key'] = self.api_key
        params.update(kwargs)
        if signature:
            params['api_sig'] = self.build_signature(params.items())
        params['format'] = 'json'
        r = requests.get(API_ROOT, params=params)
        json_resp = r.json()
        if 'error' in json_resp:
            print "Error Message:", json_resp['message']
            raise APIException(str(json_resp['error']))
        return r

    def get_request_token(self):
        method = 'auth.gettoken'
        json_resp = self.get(method, signature=True).json()
        return json_resp['token']

    def get_session(self):
        request_token = self.get_request_token()
        self.authorize_user(request_token)
        method = 'auth.getSession'
        json_resp = self.get(method, signature=True, token=request_token).json()
        return json_resp['session']

    def authorize_user(self, request_token):
        from webbrowser import open as wb_open
        wb_open("http://www.last.fm/api/auth/?api_key={0}&token={1}".format(self.api_key, request_token))
        raw_input("Press any button once you have authorized MusiGraph to use your Last.fm account")

    def get_top_artists(self):
        method = 'user.gettopartists'
        user = self.username
        limit = 50
        period = 'overall'
        json_resp = self.get(method, user=user, limit=limit, period=period).json()
        return json_resp['topartists']['artist']

    def get_similar_artists(self, artist):
        method = 'artist.getSimilar'
        limit = 10
        json_resp = self.get(method, artist=artist, limit=limit).json()
        return json_resp['similarartists']['artist']

def build_graph(nodes, edges):
    G = nx.Graph()
    G.add_nodes_from(nodes)
    for name, obj in nodes.iteritems():
        color_tuple = obj.get_color()
        color_dict = {'a':1.0, 'r':color_tuple[0], 'g':color_tuple[1], 'b':color_tuple[2]}
        viz_dict = {'color':color_dict, 'size': obj.get_value()}
        G.node[name]['viz']= viz_dict
    G.add_edges_from(edges)
    return G

def get_similar_artists(lastfm, artists):
    output_list = []
    for artist in artists:
        similar_artists = lastfm.get_similar_artists(artist)
        similar_artists = map(lambda x: x['name'], similar_artists)
        output_list.append((artist, similar_artists))
    return output_list

class Node():
    def __init__(self, name, value=1, color=(84, 84, 84)):
        self.name = name
        self.value = value
        self.color = color

    def get_name(self):
        return self.name

    def get_value(self):
        return self.value

    def get_color(self):
        return self.color

    def set_value(self, value):
        self.value = value

    def set_color(self, color):
        self.color = color

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="path to alternate config file", default="./config.json", type=str)
    args = parser.parse_args()

    lastfm = LastFm(args.config)
    artists = lastfm.get_top_artists()
    artists = map(lambda x: x['name'], artists)
    similar_artists = get_similar_artists(lastfm, artists)
    edges = []
    nodes = {}
    map(lambda row: row[0], similar_artists)
    for row in similar_artists:
        if row[0] not in nodes:
            nodes[row[0]] = Node(row[0], color=(0,0,205))
        else:
            node = nodes[row[0]]
            node.set_value(node.get_value() + 1)
            node.set_color((0,0,205))
        for similar_artist in row[1]:
            if similar_artist not in nodes:
                nodes[similar_artist] = Node(similar_artist, color=(238,0,0))
            else:
                node = nodes[similar_artist]
                node.set_value(node.get_value() + 1)
            edges.append((row[0], similar_artist))
    graph = build_graph(nodes, edges)
    nx.write_gexf(graph,'graph.gexf')
    
if __name__ == "__main__":
    main()
