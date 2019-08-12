import time
import json
import rapidjson
import pickle

d = {}

for x in range(10000):
    d['tests' + str(x)] = 'this is a test ' + str(x)
    d['testi' + str(x)] = int(x)
    d['testf' + str(x)] = float(x)

print('generated')


def test_json():
    json.dumps(d)


def test_rapidjson():
    rapidjson.dumps(d)


def test_pickle():
    pickle.dumps(d)


tests = [test_json, test_rapidjson, test_pickle]

for t in tests:
    t_start = time.time()
    iters = 100
    for z in range(iters):
        t()
    print('{}: {:.3f} ms'.format(t.__name__,
                                (time.time() - t_start) / iters * 1000))
