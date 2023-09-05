from flask import Flask, request, jsonify
from gensim.models import TfidfModel
import collections
import pandas as pd
import numpy as np
from functools import reduce
from pprint import pprint

app = Flask(__name__)

# 读取数据集和模型
_tags = pd.read_csv("./datasets/healthy-sql/t_comment.csv", usecols=range(2,4)).dropna()
tags = _tags.groupby("essay_id").agg(list)
essay_id_to_category = pd.read_csv('./datasets/healthy-sql/t_health_category.csv',usecols=range(0, 2)).dropna()
essay = pd.read_csv('./datasets/healthy-sql/t_essay.csv',usecols=range(0,3)).dropna()

# 数据预处理
essay = pd.merge(essay, essay_id_to_category, left_on='essay_type', right_on='id', how='left')
essay = essay[['id_x', 'title_x', 'title_y']].rename(columns={'id_x': 'essay_id', 'title_x': 'title', 'title_y': 'category'})

essayIndex = set(essay.index) & set(tags.index)
new_tags = tags.loc[list(essayIndex)]
ret = essay.join(new_tags)

essay_dataset = pd.DataFrame(
    map(
        lambda x: (x[1], x[2], x[3], x[4]+[x[3]]) if x[4] is not np.nan else (x[1], x[2], x[3], []),
        ret.itertuples()
    ),
    columns=["essayId", "title", "category", "comments"]
)
essay_dataset.set_index("essayId", inplace=True)

# 创建文章特征向量
def create_essay_profile(essay_dataset):
    dataset = essay_dataset["comments"].values

    from gensim.corpora import Dictionary
    dct = Dictionary(dataset)
    corpus = [dct.doc2bow(line) for line in dataset]
    model = TfidfModel(corpus)

    _essay_profile = []
    for i, data in enumerate(essay_dataset.itertuples()):
        mid = data[0]
        title = data[1]
        genres = data[2]
        vector = model[corpus[i]]
        essay_tags = sorted(vector, key=lambda x: x[1], reverse=True)[:30]
        topN_tags_weights = dict(map(lambda x: (dct[x[0]], x[1]), essay_tags))
        topN_tags_weights[genres] = 1.0
        topN_tags = [i[0] for i in topN_tags_weights.items()]
        _essay_profile.append((mid, title, topN_tags, topN_tags_weights))

    essay_profile = pd.DataFrame(_essay_profile, columns=["essayId", "title", "profile", "weights"])
    essay_profile.set_index("essayId", inplace=True)
    return essay_profile

essay_profile = create_essay_profile(essay_dataset)

# 创建倒排索引
def create_inverted_table(essay_profile):
    inverted_table = {}
    for mid, weights in essay_profile["weights"].items():
        for tag, weight in weights.items():
            _ = inverted_table.get(tag, [])
            _.append((mid, weight))
            inverted_table.setdefault(tag, _)
    return inverted_table

inverted_table = create_inverted_table(essay_profile)

# 读取用户浏览记录，构建用户画像
watch_record = pd.read_csv("datasets/healthy-sql/t_user_browsing_history.csv", usecols=range(1,3), dtype={"user_id":np.int32, "essay_id": np.int32})
watch_record = watch_record.groupby("user_id").agg(list)
user_profile = {}
for user_id, essay_id in watch_record.itertuples():
    record_movie_prifole = essay_profile.loc[list(essay_id)]
    counter = collections.Counter(reduce(lambda x, y: list(x)+list(y), record_movie_prifole["profile"].values))
    interest_words = counter.most_common(30)
    maxcount = interest_words[0][1]
    interest_words = [(w, round(c/maxcount, 4)) for w, c in interest_words]
    user_profile[user_id] = interest_words

# 推荐文章给用户
def get_commend_essay_by_user_id(user_id):
    uid = user_id
    interest_words = user_profile[uid]
    result_table = {}
    for interest_word, interest_weight in interest_words:
        related_movies = inverted_table[interest_word]
        for mid, related_weight in related_movies:
            _ = result_table.get(mid, [])
            _.append(interest_weight * related_weight)
            result_table.setdefault(mid, _)
    rs_result = map(lambda x: (x[0], sum(x[1])), result_table.items())
    rs_result = sorted(rs_result, key=lambda x:x[1], reverse=True)[:30]
    return rs_result

@app.route('/recommend', methods=['POST'])
def recommend_essay():
    # 从请求中获取 userId
    user_id = request.json.get('userId')

    # 调用 get_commend_essay_by_user_id 函数获取推荐结果
    result = get_commend_essay_by_user_id(user_id)

    # 将结果返回给客户端
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=11080)
