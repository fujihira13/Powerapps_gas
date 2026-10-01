"""Evaluate the generated rejection expression offline; no real API calls."""
import re
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'flow-implementation'))
from build_flow_definition import _log_validation_reason_expression

def parse(expression):
    tokens=re.findall(r"'[^']*'|[A-Za-z_][A-Za-z0-9_]*|\d+|[(),?\[\]]",expression.lstrip('@'))
    index=0
    def term():
        nonlocal index
        token=tokens[index]; index+=1
        if token.startswith("'"): node=('value',token[1:-1])
        elif token.isdigit(): node=('value',int(token))
        else:
            assert tokens[index]=='('; index+=1
            args=[]
            while tokens[index]!=')':
                args.append(term())
                if tokens[index]==',': index+=1
            index+=1; node=('call',token,args)
        while index<len(tokens) and tokens[index]=='?':
            index+=1; assert tokens[index]=='['; index+=1
            key=term(); assert tokens[index]==']'; index+=1
            node=('lookup',node,key)
        return node
    result=term(); assert index==len(tokens)
    return result

def evaluate(node,outputs):
    if node[0]=='value': return node[1]
    if node[0]=='lookup':
        value=evaluate(node[1],outputs); key=evaluate(node[2],outputs)
        if isinstance(value,list): return value[key] if key<len(value) else None
        return value.get(key) if value else None
    _,name,args=node
    if name=='if': return evaluate(args[1] if evaluate(args[0],outputs) else args[2],outputs)
    values=[evaluate(a,outputs) for a in args]
    functions={'outputs':lambda k:outputs[k],'greater':lambda a,b:a>b,'length':len,
        'empty':lambda a:not a,'not':lambda a:not a,'equals':lambda a,b:a==b,
        'startsWith':lambda a,b:a.startswith(b),'string':lambda a:'' if a is None else str(a),
        'coalesce':lambda *a:next((v for v in a if v is not None),None),
        'concat':lambda *a:''.join(a)}
    return functions[name](*values)

class DateIndependentTests(unittest.TestCase):
    expression=parse(_log_validation_reason_expression())
    def reason(self,log,name='sample.txt'):
        return evaluate(self.expression,{'Compose_LogText':log,'Compose_LogFileName':name,
            'Compose_LogLines':log.splitlines(),'Get_case':{'body/cr6cb_environment':'架空環境A','body/cr6cb_server':'架空サーバーA'}})
    def test_new_inputs_without_dates(self):
        for variant in ['success','missing']:
            log=(Path(__file__).resolve().parents[2]/f'outputs/flow-implementation/test-fixtures/date-independent/mq-{variant}.txt').read_text(encoding='utf-8')
            self.assertEqual(self.reason(log),'')
    def test_old_or_invalid_date_header_does_not_gate_comparison(self):
        for date in ['1999-01-01','not-a-date']:
            self.assertEqual(self.reason(f'処理日: {date}\n環境: 架空環境A\nサーバー: 架空サーバーA\nMQ_BOX_ID=MQ-1001'),'')
    def test_wrong_environment_and_server_still_stop(self):
        self.assertIn('環境が',self.reason('環境: 別環境\nサーバー: 架空サーバーA'))
        self.assertIn('サーバーが',self.reason('環境: 架空環境A\nサーバー: 別サーバー'))
    def test_missing_headers_name_and_oversize_still_stop(self):
        self.assertIn('識別情報',self.reason('MQ_BOX_ID=MQ-1001'))
        self.assertIn('ファイル名',self.reason('',''))
        self.assertIn('30,000',self.reason('x'*30001))

if __name__=='__main__': unittest.main()
