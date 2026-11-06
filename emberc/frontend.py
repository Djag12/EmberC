#!/usr/bin/env python3
"""EmberC: a deliberately small C subset -> x86-64 SysV GNU assembly.
int is signed 32-bit. One int main(void), initialized locals, block scopes,
if/else, while, break/continue, return, assignment, integer expressions.
"""
import argparse
import json
import re
from pathlib import Path

class CompileError(ValueError):
    pass

TOKEN = re.compile(r'(?P<ws>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<num>\d+)|(?P<id>[A-Za-z_]\w*)|(?P<op><<=|>>=|\+\+|--|[+*/%&|^\-]=|<<|>>|==|!=|<=|>=|&&|\|\||[{}(),;=+*/%<>!~&|^\-])')
KEYWORDS = {'int','main','void','if','else','while','return','break','continue','for','do'}

def lex(source):
    out,pos,line=[],0,1
    while pos<len(source):
        m=TOKEN.match(source,pos)
        if not m:raise CompileError(f'line {line}: unexpected character {source[pos]!r}')
        if m.lastgroup not in ('ws','comment'):out.append((m.group(),line))
        line+=m.group().count('\n');pos=m.end()
    return out+[('<eof>',line)]

class Parser:
    precedence = {'||':1,'&&':2,'|':3,'^':4,'&':5,'==':6,'!=':6,'<':7,'<=':7,'>':7,'>=':7,'<<':8,'>>':8,'+':9,'-':9,'*':10,'/':10,'%':10}
    def __init__(self,source):
        self.tokens=lex(source); self.i=0; self.scopes=[]; self.slots=0; self.loops=0
    def peek(self): return self.tokens[self.i][0]
    def fail(self,msg): raise CompileError(f'line {self.tokens[self.i][1]}: {msg}')
    def take(self,t=None):
        v=self.peek()
        if t is not None and v!=t:self.fail(f'expected {t!r}, got {v!r}')
        self.i+=1; return v
    def name(self):
        v=self.peek()
        if not re.fullmatch(r'[A-Za-z_]\w*',v) or v in KEYWORDS:self.fail('expected local variable name')
        return self.take()
    def lookup(self,name):
        for scope in reversed(self.scopes):
            if name in scope:
                if scope[name] is None:self.fail(f'variable {name!r} used in its own initializer')
                return scope[name]
        self.fail(f'undeclared variable {name!r}')
    def parse(self):
        self.take('int');self.take('main');self.take('(')
        if self.peek()=='void':self.take()
        self.take(')');node=self.block();self.take('<eof>')
        return node,self.slots
    def block(self):
        self.take('{');self.scopes.append({});out=[]
        while self.peek()!='}':
            if self.peek()=='<eof>':self.fail('unterminated block')
            out.append(self.statement())
        self.take('}');self.scopes.pop();return ['block',out]
    def statement(self):
        t=self.peek()
        if t=='{':return self.block()
        if t==';':self.take();return ['empty']
        if t=='int':
            self.take();name=self.name()
            if name in self.scopes[-1]:self.fail(f'duplicate declaration {name!r}')
            self.scopes[-1][name]=None
            self.take('=');expr=self.expression();self.take(';')
            # Reject self-initialization, including a shadowing declaration.
            self.slots+=1;slot=self.slots;self.scopes[-1][name]=slot
            return ['set',slot,expr]
        if t=='return':
            self.take();expr=self.expression();self.take(';');return ['return',expr]
        if t=='if':
            self.take();self.take('(');cond=self.expression();self.take(')')
            yes=self.control_body();no=['empty']
            if self.peek()=='else':self.take();no=self.control_body()
            return ['if',cond,yes,no]
        if t=='while':
            self.take();self.take('(');cond=self.expression();self.take(')');self.loops+=1
            body=self.control_body();self.loops-=1;return ['while',cond,body]
        if t=='for':
            self.take();self.take('(');self.scopes.append({})
            init=self.statement() if self.peek()=='int' else self.simple_statement(';')
            cond=['number',1] if self.peek()==';' else self.expression();self.take(';')
            step=self.simple_statement(')');self.loops+=1
            body=self.control_body();self.loops-=1;self.scopes.pop()
            return ['for',init,cond,step,body]
        if t=='do':
            self.take();self.loops+=1;body=self.control_body();self.loops-=1
            self.take('while');self.take('(');cond=self.expression();self.take(')');self.take(';')
            return ['do',body,cond]
        if t in ('break','continue'):

            if not self.loops:self.fail(t+' outside loop')
            self.take();self.take(';');return [t]
        return self.simple_statement(';')
    def simple_statement(self,end):
        if self.peek()==end:self.take();return ['empty']
        assignments={'=','+=','-=','*=','/=','%=','&=','|=','^=','<<=','>>='}
        if self.i+1<len(self.tokens) and self.tokens[self.i+1][0] in assignments:
            name=self.name();slot=self.lookup(name);op=self.take();expr=self.expression()
            if op!='=':expr=['binary',op[:-1],['var',slot],expr]
            self.take(end);return ['set',slot,expr]
        expr=self.expression();self.take(end);return ['expr',expr]

    def control_body(self):
        # A declaration as an unbraced control body is not valid C.
        if self.peek()=='int':self.fail('declaration requires a block here')
        return self.statement()
    def expression(self,min_prec=1):
        if self.peek() in ('++','--'):
            op=self.take();slot=self.lookup(self.name());lhs=['update',slot,1 if op=='++' else -1,False]
        elif self.peek() in ('-','+','!','~'):
            op=self.take();lhs=['unary',op,self.expression(11)]
        elif self.peek()=='(':
            self.take();lhs=self.expression();self.take(')')
        elif self.peek().isdigit():
            v=int(self.take())
            if v>2147483647:self.fail('integer literal exceeds signed 32-bit range')
            lhs=['number',v]
        else:
            name=self.name()
            if getattr(self,'allow_calls',False) and self.peek()=='(':
                self.take('(');args=[]
                if self.peek()!=')':
                    args.append(self.expression())
                    while self.peek()==',':self.take(',');args.append(self.expression())
                self.take(')');lhs=['call',name,args]
            else:lhs=['var',self.lookup(name)]
        if self.peek() in ('++','--'):
            if lhs[0]!='var':self.fail('increment requires a variable')
            op=self.take();lhs=['update',lhs[1],1 if op=='++' else -1,True]
        while self.precedence.get(self.peek(),0)>=min_prec:
            op=self.take();rhs=self.expression(self.precedence[op]+1);lhs=['binary',op,lhs,rhs]
        return lhs

class Generator:
    def __init__(self):self.lines=[];self.n=0;self.loops=[]
    def emit(self,*lines):self.lines.extend(lines)
    def label(self):self.n+=1;return '.L'+str(self.n)
    def expr(self,n):
        kind=n[0]
        if kind=='number':self.emit(f' movl ${n[1]}, %eax')
        elif kind=='var':self.emit(f' movl -{n[1]*8}(%rbp), %eax')
        elif kind=='unary':
            self.expr(n[2])
            if n[1]=='-':self.emit(' negl %eax')
            elif n[1]=='~':self.emit(' notl %eax')
            elif n[1]=='!':self.emit(' testl %eax, %eax',' sete %al',' movzbl %al, %eax')
        elif kind=='binary':
            op=n[1]
            if op in ('&&','||'):
                short,end=self.label(),self.label();self.expr(n[2]);self.emit(' testl %eax, %eax',(' je ' if op=='&&' else ' jne ')+short)
                self.expr(n[3]);self.emit(' testl %eax, %eax',' setne %al',' movzbl %al, %eax',' jmp '+end,short+':',f' movl ${0 if op=="&&" else 1}, %eax',end+':');return
            self.expr(n[2]);self.emit(' pushq %rax');self.expr(n[3]);self.emit(' movl %eax, %ecx',' popq %rax')
            arithmetic={'+':' addl %ecx, %eax','-':' subl %ecx, %eax','*':' imull %ecx, %eax','&':' andl %ecx, %eax','|':' orl %ecx, %eax','^':' xorl %ecx, %eax','<<':' sall %cl, %eax','>>':' sarl %cl, %eax'}
            if op in arithmetic:self.emit(arithmetic[op])
            elif op in ('/','%'):
                self.emit(' cltd',' idivl %ecx')
                if op=='%':self.emit(' movl %edx, %eax')
            else:
                suffix={'==':'e','!=':'ne','<':'l','<=':'le','>':'g','>=':'ge'}[op]
                self.emit(' cmpl %ecx, %eax',f' set{suffix} %al',' movzbl %al, %eax')
        else:raise CompileError('Use the WASM backend for this expression')
    def stmt(self,n):
        k=n[0]
        if k=='block':
            for x in n[1]:self.stmt(x)
        elif k=='set':self.expr(n[2]);self.emit(f' movl %eax, -{n[1]*8}(%rbp)')
        elif k=='return':self.expr(n[1]);self.emit(' jmp .Lreturn')
        elif k=='if':
            no,end=self.label(),self.label();self.expr(n[1]);self.emit(' testl %eax, %eax',' je '+no);self.stmt(n[2]);self.emit(' jmp '+end,no+':');self.stmt(n[3]);self.emit(end+':')
        elif k=='while':
            start,end=self.label(),self.label();self.loops.append((start,end));self.emit(start+':');self.expr(n[1]);self.emit(' testl %eax, %eax',' je '+end);self.stmt(n[2]);self.emit(' jmp '+start,end+':');self.loops.pop()
        elif k in ('break','continue'):self.emit(' jmp '+self.loops[-1][k=='break'])
        elif k!='empty':raise CompileError('Use the WASM backend for this statement')
    def generate(self,tree,slots):
        size=((slots*8+15)//16)*16
        self.emit('.text','.globl main','main:',' pushq %rbp',' movq %rsp, %rbp',f' subq ${size}, %rsp')
        self.stmt(tree);self.emit(' xorl %eax, %eax','.Lreturn:',' leave',' ret','.section .note.GNU-stack,"",@progbits')
        return '\n'.join(self.lines)+'\n'

def compile_source(source):
    tree,slots=Parser(source).parse();return Generator().generate(tree,slots)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('-o','--output',type=Path,required=True);ap.add_argument('--ast',type=Path);ap.add_argument('--optimize',action='store_true');a=ap.parse_args()
    try:
        tree,slots=Parser(a.source.read_text()).parse()
        if a.optimize:
            from optimizer import optimize
            tree=optimize(tree)
        assembly=Generator().generate(tree,slots)
        a.output.write_text(assembly)
        if a.ast:a.ast.write_text(json.dumps(tree,indent=2)+'\n')
    except (OSError,CompileError) as exc:ap.exit(1,f'emberc: {exc}\n')
if __name__=='__main__':main()
