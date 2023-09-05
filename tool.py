import mysql.connector
from gensim.models import TfidfModel
import collections
import pandas as pd
from functools import reduce


# connect 数据库sql


def execute_query(query):
    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="Gjm9478402",
        database="healthPlatform"
    )

    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    return result


def read_essay_data():
    query = "SELECT e.id, e.title, c.title AS category " \
            "FROM t_essay AS e " \
            "INNER JOIN t_health_category AS c ON e.essay_type = c.id"

    essay_data = execute_query(query)

    essay_dataset = pd.DataFrame(
        essay_data,
        columns=["essayId", "title", "category"]
    )
    essay_dataset.set_index("essayId", inplace=True)

    return essay_dataset


def read_comment_data():
    query = "SELECT essay_id, comment FROM t_comment"

    comment_data = execute_query(query)

    comment_dataset = pd.DataFrame(
        comment_data,
        columns=["essayId", "comment"]
    )

    comments_grouped = comment_dataset.groupby("essayId")["comment"].apply(list)

    return comments_grouped


def read_user_browsing_history():
    # 从数据库中读取用户浏览历史记录
    query = "SELECT user_id, essay_id FROM t_user_browsing_history"
    watch_record_data = execute_query(query)

    # 创建DataFrame存储用户浏览历史记录
    watch_record = pd.DataFrame(
        watch_record_data,
        columns=["user_id", "essay_id"]
    )
    return watch_record


def create_essay_dataset():
    essay_dataset = read_essay_data()
    comments_grouped = read_comment_data()
    essay_dataset["comments"] = comments_grouped
    essay_dataset["comments"] = essay_dataset["comments"].fillna('').apply(lambda x: x if isinstance(x, list) else [])
    return essay_dataset


# 文章画像
def create_essay_profile(essay_dataset):

    # 使用tfidf，分析提取topn关键词


    dataset = essay_dataset["comments"].values

    from gensim.corpora import Dictionary
    # 根据数据集建立词袋，并统计词频，将所有词放入一个词典，使用索引进行获取
    dct = Dictionary(dataset)
    # 根据将每条数据，返回对应的词索引和词频
    corpus = [dct.doc2bow(line) for line in dataset]
    # 训练TF-IDF模型，即计算TF-IDF值
    model = TfidfModel(corpus)

    _essay_profile = []
    for i, data in enumerate(essay_dataset.itertuples()):
        mid = data[0]
        title = data[1]
        genres = data[2]
        vector = model[corpus[i]]
        essay_tags = sorted(vector, key=lambda x: x[1], reverse=True)[:30]
        topN_tags_weights = dict(map(lambda x: (dct[x[0]], x[1]), essay_tags))
        # 将类别词的添加进去，并设置权重值为1.0
        topN_tags_weights[genres] = 1.0
        topN_tags = [i[0] for i in topN_tags_weights.items()]
        _essay_profile.append((mid, title, topN_tags, topN_tags_weights))

    essay_profile = pd.DataFrame(_essay_profile, columns=["essayId", "title", "profile", "weights"])
    essay_profile.set_index("essayId", inplace=True)
    return essay_profile


# 倒排表
def create_inverted_table(essay_profile):
    inverted_table = {}
    for mid, weights in essay_profile["weights"].items():
        for tag, weight in weights.items():
            # 到inverted_table dict 用tag作为Key去取值 如果取不到就返回[]
            _ = inverted_table.get(tag, [])
            _.append((mid, weight))
            inverted_table.setdefault(tag, _)
    return inverted_table


# 调用函数读取数据集


# 用户画像
def create_user_profile(essay_profile):
    watch_record = read_user_browsing_history()
    watch_record = watch_record.groupby("user_id").agg(list)
    user_profile = {}
    for user_id, essay_id in watch_record.itertuples():
        # 从文章词权重中取出用户看过的
        record_essay_prifole = essay_profile.loc[list(essay_id)]
        # reduce 聚合
        counter = collections.Counter(reduce(lambda x, y: list(x) + list(y), record_essay_prifole["profile"].values))

        # 兴趣词
        interest_words = counter.most_common(30)
        maxcount = interest_words[0][1]
        # 除以看到词汇最大次数
        interest_words = [(w, round(c / maxcount, 4)) for w, c in interest_words]
        user_profile[user_id] = interest_words
    return user_profile


def get_commend_essay_by_user_id(user_id,inverted_table,user_profile):
    uid = user_id
    interest_words = user_profile[uid]
    result_table = {}
    for interest_word, interest_weight in interest_words:
        related_essay = inverted_table[interest_word]
        for mid, related_weight in related_essay:
            _ = result_table.get(mid, [])
            _.append(interest_weight * related_weight)
            result_table.setdefault(mid, _)
    rs_result = map(lambda x: (x[0], sum(x[1])), result_table.items())
    rs_result = sorted(rs_result, key=lambda x: x[1], reverse=True)[:30]
    return rs_result
