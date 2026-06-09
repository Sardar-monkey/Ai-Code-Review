"""A simple calculator with some code quality issues."""

def calc(a, b, op):
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        return a / b
    elif op == '^':
        # Power operation
        result = 1
        for i in range(b):
            result = result * a
        return result
    else:
        return None

def process_data(data):
    result = []
    for i in range(len(data)):
        item = data[i]
        if item != None:
            if type(item) == int or type(item) == float:
                result.append(calc(item, 2, '*'))
            elif type(item) == str:
                result.append(item.upper())
            else:
                result.append(item)
    return result

def save_results(data, filename):
    f = open(filename, 'w')
    for item in data:
        f.write(str(item) + '\n')
    f.close()

def read_config(path):
    # This could fail if file doesn't exist
    exec(open(path).read())

def main():
    x = 10
    y = 0
    print(calc(x, y, '/'))  # Division by zero!
    
    items = [1, 2, None, 'hello', 3, [1,2,3]]
    processed = process_data(items)
    save_results(processed, 'output.txt')
    
    # This is dangerous
    read_config('config.py')

if __name__ == '__main__':
    main()
