import hashlib # hash 함수용 sha256 사용할 라이브러리
import json
import requests
from time import time
from urllib.parse import urlparse
from flask import Flask, request, jsonify
import json
from uuid import uuid4

class Blockchain(object):
    def __init__(self):
        self.chain = [] # chain에 여러 block들 들어옴
        self.current_transaction = [] # 임시 transaction 넣어줌 
        self.nodes = set() # node목록 보관 (port 기준으로 구분하기 위함), 같은 노드일 경우, 정확히 한번만 저장하게 됨

        # genesis block 생성 
        self.new_block(previous_hash=1, proof=100)

    def new_block(self, proof, previous_hash=None):
        # 블록체인에 들어갈 새로운 블록을 만드는 코드이다.
        # index는 블록의 번호, timestamp는 블록이 만들어진 시간이다.
        # transaction은 블록에 포함될 거래이다.
        # proof는 논스값이고, previous_hash는 이전 블록의 해시값이다.

        block = {
            'index' : len(self.chain)+1,
            'timestamp' : time(), 
            'transactions' : self.current_transaction,
            'proof' : proof,
            'previous_hash' : previous_hash or self.hash(self.chain[-1])
        } # 블록의 구조
        self.current_transaction = [] # 임시 transaction 넣어줌 
        self.chain.append(block) # chain에 block 삽입 
        return block # block 구조 반환 

    def new_transaction(self, sender, recipient, amount):
        # 새로운 거래는 다음으로 채굴될 블록에 포함되게 된다. 거래는 3개의 인자로 구성되어 있다. 
        # sender와 recipient는 string으로 각각 수신자와 송신자의 주소이다. 
        # amount는 int로 전송되는 양을 의미한다. return은 해당 거래가 속해질 블록의 숫자를 의미한다.

        self.current_transaction.append(
            {
                'sender' : sender, # 송신자
                'recipient' : recipient, # 수신자
                'amount' : amount # 금액
            }
        )
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block): 
        # SHA-256을 이용하여 블록의 해시값을 구한다.
        # 해시값을 만드는데 block이 input 값으로 사용된다.

        block_string = json.dumps(block, sort_keys=True).encode()

        # hash 라이브러리로 sha256 사용
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        # 체인의 마지막 블록을 반환한다. 

        return self.chain[-1]

    def pow(self, last_proof): # 작업증명 (Proof-of-Work)
        # 작업증명에 대한 간단한 설명이다:
        # - p는 이전 값, p'는 새롭게 찾아야 하는 값이다. 
        # - hash(pp')의 결과값이 첫 4개의 0으로 이루어질 때까지 p'를 찾는 과정이 작업 증명과정이다. 

        proof = 0
        # valid proof 함수를 통해 맞을 때까지 반복적으로 검증
        while self.valid_proof(last_proof, proof) is False:
            proof += 1 # proof 증가

        return proof # proof 반환 

    @staticmethod
    def valid_proof(last_proof, proof):
        # 작업증명 결과값을 검증하는 코드이다. hash(p,p')값의 앞의 4자리가 0으로 이루어져 있는가를 확인한다.
        # 결과값은 boolean으로 조건을 만족하지 못하면 false가 반환된다.

        # 전 proof와 구할 proof 문자열 연결
        guess = str(last_proof + proof).encode()
        # 이 hash 값 저장
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000" # hash의 앞자리가 0000이면 = true를 반환 

    def register_node(self, address):
        # 새 노드를 node list에 저장한다. (set 함수)
        
        parsed_url = urlparse(address) # url 주소를 넣는다
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc) # url 주소를 추가한다
        else:
            raise ValueError('Invalid URL') # 잘못된 url일 경우 나오는 에러 

    def valid_chain(self,chain):
        # 노드가 보유하고 있는 체인이 유효한지를 체크하는 역할을 한다.
        # 각각의 블록의 hash값이 맞는지를 확인하여, 맞으면 true, 틀리면 false를 반환한다. 

        last_block = chain[0] # Genesis Block 저장
        current_index = 1
		
        # 전체 체인 길이만큼 반복해서 비교한다 
        while current_index < len(chain): 
            block = chain[current_index]
            print('%s' % last_block) 
            print('%s' % block)
            print("\n---------\n") # 각각의 last block와 block를 출력

            # hash 값의 비교
            last_block_hash = self.hash(last_block)
            if block['previous_hash'] != last_block_hash:
                return False # hash 값이 같지 않다면 false를 반환 

            last_block = block
            current_index += 1 

        return True # 해당 인덱스들을 저장 후 true를 반환 
            
    def resolve_conflicts(self):
        # 모든 이웃 노드들의 체인을 받고 규칙(가장 긴 체인이 맞는 체인)에 의거하여,
        # 유효한 체인(가장 긴 체인을 보유하는지)인지 확인하는 Consensus 함수이다. 
        # 만약에 valid chain 이 우리의 chain보다 더 길다면, 우리 chain은 대체된다.
        
        neighbours = self.nodes # 각 노드들을 저장하는 neighbour들   
        new_chain = None 
        
        max_length = len(self.chain) # 우리 체인의 길이 

        for node in neighbours:
            tmp_url = 'http://' + str(node) + '/chain'
            response = requests.get(tmp_url) # url을 받아서 request를 통해 chain 정보 저장

            if response.status_code == 200: # 정상적으로 request를 보내고 응답을 받았다면 
                # chain의 길이와 정보
                length = response.json()['length']
                chain = response.json()['chain']
                
                if length > max_length and self.valid_chain(chain): # 긴 chain을 비교 (어느것이 긴 chain인가?)
                    max_length = length
                    new_chain = chain

            if new_chain:
                self.chain = new_chain
                return True # 만약 상대것이 길다면 = 우리의 chain은 대체된다 (true)
            
        return False # 아니면 보존된다 (false)


app = Flask(__name__)
# Universial Unique Identifier
# 노드 식별을 하기 위해 uuid 함수를 사용한다. 
node_identifier = str(uuid4()).replace('-','')

# 블록체인 객체를 선언
blockchain = Blockchain()

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain' : blockchain.chain, # 블록체인을 출력
        'length' : len(blockchain.chain) # 블록체인 길이 출력
    }

    # json 형태로 리턴 (200 은 웹 사이트에 에러가 없을 때 터미널에서 뜨는 숫자다)
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json() # json 형태를 받아서 저장한다. 

    required = ['sender', 'recipient', 'amount'] # 필요한 값이 모두 존재하는지 확인하는 과정이다.
    
    # 데이터가 없으면 에러를 띄움
    if not all(k in values for k in required):
        return 'missing values', 400

    # 새 트랜잭션 만들고 삽입 (새로운 거래를 추가)
    index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])
    response = {'message' : 'Transaction will be added to Block {%s}' % index}

    return jsonify(response), 201 

@app.route('/mine', methods=['GET']) # 채굴
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof'] 
    proof = blockchain.pow(last_proof) # PoW 알고리즘을 사용한다 (다음 Proof를 얻기 위함)

    # 채굴에 대한 보상 설정
    blockchain.new_transaction(
        sender='0', # 채굴시 생성되는 transaction (송신자를 0으로 표현한 것은 블록 채굴에 대한 보상이기 때문)
        recipient=node_identifier, # 지갑 주소처럼 사용
        amount=1 # coinbase transaction: 채굴할 때마다 1 코인씩 준다
    )

    # 체인에 새로운 블록을 추가하는 코드이다. 
    # 전 블록에 대한 hash를 떠놓고
    previous_hash = blockchain.hash(last_block)
    # 검증을 넣어서 블록을 새로 생성
    block = blockchain.new_block(proof, previous_hash)

    # block 이 제대로 mine 되었다는 정보를 json 형태로 띄워줌
    response = {
        'message' : 'new block found',
        'index' : block['index'],
        'transactions' : block['transactions'],
        'proof' : block['proof'],
        'previous_hash' : block['previous_hash']
    }

    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
	values = request.get_json() # json 형태를 통해 노드의 정보를 보냄 

	nodes = values.get('nodes')
	if nodes is None: # 입력받은 노드가 없다면 = 400을 띄우고 Err
		return "Error: Please supply a valid list of nodes", 400

	for node in nodes:
		blockchain.register_node(node) # 노드 등록 

	response = {
		'message' : 'New nodes have been added',
		'total_nodes': list(blockchain.nodes), # Node의 추가를 보여줌
	}
	return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
	replaced = blockchain.resolve_conflicts() # 상기 함수에서 True False 결과값을 받아온다 
    
    # chain 변경을 알리는 메시지 
	if replaced:
		response = {
			'message' : 'Our chain was replaced',
			'new_chain' : blockchain.chain # 합의 알고리즘을 통해 chain이 변경되었을 경우
		}
	else:
		response = {
			'message' : 'Our chain is authoritative',
			'chain' : blockchain.chain # chain이 변경되지 않았을 경우
		}
	return jsonify(response), 200

# 서버의 url, port는 자신이 원하는 port번호를 설정한다.(여기서는 5000) 
# 주소는 localhost:port이다.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 