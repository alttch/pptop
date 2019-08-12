import time
import json
import rapidjson
import pickle
import _pickle as cPickle

d = {}

for x in range(100000):
    d['test' + str(x)] = 'this is a test'
    d['testi' + str(x)] = x

print('generated')

def test_json():
    json.dumps(d)

def test_rapidjson():
    rapidjson.dumps(d)

def test_pickle():
    pickle.dumps(d)

def test_cpickle():
    cPickle.dumps(d)

tests = [test_json, test_rapidjson, test_pickle, test_cpickle]

for t in tests:
    t_start = time.time()
    for z in range(100):
        t()
    print('{}: {}'.format(t.__name__, time.time() - t_start))
