from flask import Flask

app = Flask(__name__)

@app.route('/execute', methods=['GET'])
def execute():
    # 在这里执行您的操作，并返回结果
    result = "Hello, World!"  # 示例结果

    return result

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
