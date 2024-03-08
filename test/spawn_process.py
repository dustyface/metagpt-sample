from subprocess import Popen

def main():
    urls = ["https://www.baidu.com", "https://www.google.com"]
    # Popen(["nohup", "python", "./test/sub_process.py", str(urls), "helloworld", "&"])
    Popen(["python", "./test/sub_process.py", str(urls), "helloworld"])
    print("main end")

main()