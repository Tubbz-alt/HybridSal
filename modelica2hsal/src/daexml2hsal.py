"Convert DAE XML into HybridSal"

import xml.dom.minidom
import xml.parsers.expat
import sys
import os.path
import daexmlPP
import ddae

def valueOf(node):
    """return text value of node"""
    for i in node.childNodes:
        if i.nodeType == i.TEXT_NODE:
            return(i.data)

def getArg(node,index):
    j = 0
    for i in node.childNodes:
        if (i.nodeType == i.ELEMENT_NODE):
            j = j+1
            if j == index:
                return(i)
    return None

def helper_create_tag_val(tag, val, position = None):
    global dom
    node = dom.createElement(tag)
    if position != None:
        node.setAttribute('col', str(position.col))
        node.setAttribute('line', str(position.line))
    node.appendChild( dom.createTextNode( val ) )
    return node 

def replace(node, newnode, root):
    '''replace node by newnode and call simplify'''
    if node == root:	# I am the expr
        root = newnode
    else:
        parentnode = node.parentNode
        parentnode.replaceChild(newChild=newnode,oldChild=node)
        # root = simplify(parentnode, newnode, root)
    return root

def getPredsInConds(contEqns):
    '''get all predicates used in IF conditions'''
    def add2Preds(preds, name, val):
        if preds.has_key(name):
            if val != None and val not in preds[name]:
                preds[name].append(val)
        else:
            preds[name] = [] if val == None else [val]
        return preds
    def getPredsInBapp(c, preds):
        op = getArg(c, 1)
        a1 = getArg(c, 2)
        a2 = getArg(c, 3)
        s1 = valueOf(op).strip()
        if a1.tagName in ['identifier','pre'] and a2.tagName == 'number':
            name = valueOf(a1).strip() if a1.tagName == 'identifier' else valueOf(getArg(a1,1)).strip()
            # print 'trying to add {0}'.format(name)
            return add2Preds(preds, name, float(valueOf(a2)))
        elif s1 in ['or', 'and']:
            preds = getPredsInExpr(a1, preds)
            preds = getPredsInExpr(a2, preds)
            return preds
        elif s1 in ['>', '<'] and a2.tagName == 'number' and a1.tagName == 'BAPP':
            s11 = valueOf(getArg(a1,1)).strip()
            a11 = getArg(a1,2)
            a12 = getArg(a1,3)
            if a12.tagName == 'identifier' and a11.tagName == 'number':
                name = valueOf(a12).strip()
                val1 = float(valueOf(a11))
                val2 = float(valueOf(a2))
                if s11 == '-':
                    val = val1 - val2
                elif s11 == '+':
                    val = val2 - val1
                elif s11 == '*':
                    val = val2 / val1
                elif s11 == '/':
                    val = val1 / val2
                else:
                    assert False, 'Missing operator {0}'.format(s11)
                #print 'trying to add {0} {1}'.format(name,val)
                return add2Preds(preds, name, val)
            elif a11.tagName == 'identifier' and a12.tagName == 'identifier':
                name1 = valueOf(a11).strip()
                name2 = valueOf(a12).strip()
                val = float(valueOf(a2))
                return add2Preds(preds, (s11,name1,name2), val)
            else:
                assert False, 'MISSING BAPP CODE: Found {0} expression.'.format(daexmlPP.ppExpr(c))
        else:
            assert False, 'MISSING BAPP CODE: Found {0} expression.'.format(daexmlPP.ppExpr(c))
    def getPredsInExpr(c, preds):
        # print 'entering', preds
        if c.tagName == 'identifier':
            return add2Preds(preds, valueOf(c).strip(), None)
        elif c.tagName == 'pre':
            return getPredsInExpr(getArg(c,1), preds)
        elif c.tagName == 'number':
            assert False, 'number can not be a Boolean'
        elif c.tagName == 'INITIAL' or c.tagName == 'string':
            return preds
        elif c.tagName == 'UAPP':
            return getPredsInExpr(getArg(c,2), preds)
        elif c.tagName == 'BAPP':
            return getPredsInBapp(c, preds)
        else:
            assert False, 'MISSING CODE: Found {0} expression.'.format(c.tagName)
    def getPredsInEqn(e, preds):
        ifs = e.getElementsByTagName('IF')
        for ite in ifs:
            cond = getArg(ite,1)
            preds = getPredsInExpr(cond, preds)
        return preds
    preds = {}
    for e in contEqns:
        preds = getPredsInEqn(e, preds)
    return preds

def getElementsByTagTagName(root, tag1, tag2):
    node = root.getElementsByTagName(tag1)
    if node == None or len(node) == 0:
        return []
    nodes = node[0].getElementsByTagName(tag2)
    ans = nodes if nodes != None else []
    return ans    

def getIdentifiersIn(root, tag1):
    ids = getElementsByTagTagName(root, tag1, 'identifier')
    return [ valueOf(i).strip() for i in ids ]

def classifyEqns(eqns, cstate, dstate):
    "partition eqns into 2 sets: dx/dt=f(x) and x'=f(x)"
    def isCont(e):
        ders = e.getElementsByTagName('der')
        return ders != None and len(ders) > 0
    def isDisc(e):
        lhs = getArg(e,1)
        return lhs.tagName == 'identifier' and valueOf(lhs).strip() in dstate
    (d,c,others) = ( [], [], [])
    for e in eqns:
        if isCont(e):
            c.append(e)
        elif isDisc(e):
            d.append(e)
        else:
            others.append(e)
    return (d,c,others)

def findState(Eqn, cstate, dstate, var_details):
    "return (bools, reals, integers) from the give equations"
    def myappend(lst, v):
        if v not in lst:
            lst.append(v)
        return lst
    def find(name, allvars):
        for i in allvars:
            name1 = i.getAttribute('name')
            if name1 == name:
                return i
        print 'ERROR: Unknown variable found! Can not handle.'
        assert False, "Variable {0} not found".format(name)
        return None
    ids = Eqn.getElementsByTagName('identifier')
    bools, reals, integers = [], [], []
    nonstates, inputs = [], []
    varmap = {}
    for identifier in ids:
        name = valueOf(identifier).strip()
        ovar = find(name, var_details)
        vtype = ovar.getAttribute('type')
        variability = ovar.getAttribute('variability')
        varmap[name] = ovar
        if variability != 'continuousState' and name not in dstate:
            myappend(nonstates, name)
        direction = ovar.getAttribute('direction')
        if direction == 'input':
            myappend(inputs, name)
        if vtype == 'Real':
            myappend(reals, name)
        elif vtype == 'Boolean':
            myappend(bools, name)
        elif vtype == 'Integer':
            myappend(integers, name)
        else:
            assert False, "Type {0} not found".format(vtype)
    print 'bools', bools
    print 'reals', reals
    print 'integers', integers
    print 'inputs', inputs
    print 'nonstates', nonstates
    print 'cstate', cstate
    print 'dstate', dstate
    return (bools, reals, integers, inputs, nonstates, varmap)
 
# -----------------------------------------------------------------
def expr2sal(node, flag=True):
    opmap = {'==':'=', 'and':'AND', 'or':'OR', 'not':'NOT'}
    def op2sal(node):
        op = valueOf(node).strip()
        ans = opmap[op] if opmap.has_key(op) else op
        return ans
    if node.tagName == 'identifier':
        ans = valueOf(node).strip() 
        if ans in ['false','true','False','True']:
            ans = ans.upper()
        else:
            ans += "'" if flag else ""
        return ans
    elif node.tagName == 'pre':
        return valueOf(getArg(node,1)).strip()
    elif node.tagName == 'der':
        return valueOf(getArg(node,1)).strip() + "dot'"
    elif node.tagName == 'number' or node.tagName == 'string':
        return valueOf(node).strip()
    elif node.tagName == 'INITIAL':
        return ''
    elif node.tagName == 'BAPP':
        op = getArg(node, 1)
        a1 = getArg(node, 2)
        a2 = getArg(node, 3)
        s1 = op2sal(op)
        s2 = expr2sal(a1, flag)
        s3 = expr2sal(a2, flag)
        if s2 == '':	# hack to deal with initial()
            return s3
        if s3 == '':
            return s2
        return '(' + s2 + ')' + s1 + '(' + s3 + ')'
    elif node.tagName == 'UAPP':
        op = getArg(node, 1)
        a1 = getArg(node, 2)
        s1 = op2sal(op)
        s2 = expr2sal(a1, flag)
        return s1 + '(' + s2 + ')'
    elif node.tagName == 'IF':
        c  = getArg(node, 1)
        v1 = getArg(node, 2)
        v2 = getArg(node, 3)
        s1 = expr2sal(c, flag)
        s2 = expr2sal(v1, flag)
        s3 = expr2sal(v2, flag)
        return 'IF ' + s1 + ' THEN ' + s2 + ' ELSE ' + s3 + ' ENDIF '
    elif node.tagName == 'set':
        assert False, 'expr2sal missing code for set'
    else:
        print >> sys.stderr, 'MISSING CODE: Found {0} expression.'.format(node.tagName)
        print >> sys.stderr, 'MISSING CODE: {0}'.format(node.toprettyxml())
    return ""

def getInitialValue(vmap, var):
    if not vmap.has_key(var):
        return None
    node = vmap[var]	# node is from Modelica XML dom
    ival = node.getElementsByTagName('initialValue')
    if ival == None or len(ival) == 0:
        return None
    istr = ival[0].getAttribute('string')
    z = ddae.parse_expr(istr)
    # print 'Parsed expr as {0}'.format(z.toprettyxml())
    # convert2sal
    ans = expr2sal(z,flag=False)
    # print 'Converted to SAL as {0}'.format(ans)
    return ans

# need to handle INITIAL properly
def createControl(state, deqns, guard, dom):
    "print the control HSAL module"
    def extractInitE(eqn):
        var = getArg(eqn,1)
        val = getArg(eqn,2)
        inits = val.getElementsByTagName('INITIAL')
        if inits == None or len(inits) == 0:
            return (var,val,None)
        assert len(inits) == 1, 'Assumed atmost one initial in expression'
        init = inits[0]
        p = init.parentNode
        while p != val and p.tagName == 'BAPP' and valueOf(getArg(p,1)).strip() == 'and':
            init = p
            p = p.parentNode
        false_node = helper_create_tag_val('string','FALSE')
        val = replace(init, false_node, val)
        return (var,val,init)
    def extractInit(deqns):
        return [ extractInitE(i) for i in deqns ]
    ans = "\n control: MODULE = \n BEGIN"
    (bools,reals,ints,inputs,nonstates,vmap) = state
    for i in bools:
        ans += "\n  OUTPUT {0}: BOOLEAN".format(i)
    for i in ints:
        ans += "\n  OUTPUT {0}: NATURAL".format(i)
    for i in reals:
        ans += "\n  INPUT  {0}: REAL".format(i)
    varValInitL = extractInit(deqns)
    ans  += "\n  INITIALIZATION"
    first = True
    for (var, val, init) in varValInitL:
        lhs = expr2sal(var, flag = False)
        if init != None:
            sep = ";" if not(first) else ""
            first = False if first else first
            rhs = expr2sal(init, flag = False)
            ans += "{2}\n\t {0} = {1}".format(lhs,rhs,sep)
        else:  # get initialization from vmap[var]
            initval = getInitialValue(vmap,lhs)
            if initval != None:
                sep = ";" if not(first) else ""
                first = False if first else first
                ans += "{2}\n\t {0} = {1}".format(lhs,initval,sep)
    ans  += "\n  TRANSITION\n  ["
    guard = guard if guard != "" else "TRUE"
    ans  += "\n  {0} -->".format(guard)
    first = True
    for (var, val, init) in varValInitL:
        lhs = expr2sal(var)
        rhs = expr2sal(val)
        sep = ";" if not(first) else ""
        first = False if first else first
        ans += "{2}\n\t {0} = {1}".format(lhs,rhs,sep)
    ans += "\n  ]"
    ans += "\n END;\n"
    return ans

def helper_create_app(tag, childs):
    global dom
    node = dom.createElement(tag)
    for i in childs:
        node.appendChild( i )
    return node 

def simplifyITEeq(e1, e2, var=None):
    "e1, e2 are conditional expressions; generate condition assigment"
    def isVar(v,name):
        return v.tagName=='identifier' and valueOf(v).strip()==name
    def isBOp(v,op):
        return v.tagName=='BAPP' and valueOf(getArg(v,1)).strip()==op
    def isUOp(v,op):
        return v.tagName=='UAPP' and valueOf(getArg(v,1)).strip()==op
    def mkBOp(op,v1,v2):
        op = helper_create_tag_val('BINARY_OPERATOR',op)
        return helper_create_app('BAPP',[op,v1.cloneNode(True),v2.cloneNode(True)])
    def mkUOp(op,v1):
        op = helper_create_tag_val('UNARY_OPERATOR',op)
        return helper_create_app('UAPP',[op,v1.cloneNode(True)])
    def solve(v1, v2, var):
        if isVar(v1,var):
            return v2.cloneNode(True)
        if isVar(v2,var):
            return v1.cloneNode(True)
        if isBOp(v1,'+'):
            a1 = getArg(v1,2)
            a2 = getArg(v1,3)
            return solve(a1,mkBOp('-',v2,a2),var)
        if isBOp(v1,'-'):
            a1 = getArg(v1,2)
            a2 = getArg(v1,3)
            return solve(a1, mkBOp('+',v2,a2), var)
        if isBOp(v1,'*'):
            a1 = getArg(v1,2)
            a2 = getArg(v1,3)
            return solve(a2, mkBOp('/',v2,a1), var)
        if isUOp(v1,'-'):
            a1 = getArg(v1,2)
            return solve(a1, mkUOp('-',v2), var)
        print 'Unable to solve equation'
        assert False, 'Expr is {0}'.format(daexmlPP.ppExpr(v1))
    assert len(e1) > 0, 'Error: expecting nonempty list'
    (c0,d0,v0) = e1[0]
    if var == None and v0.tagName == 'identifier':
        var = valueOf(v0).strip()
    assert var != None, 'Error: Cant handle arbitrary equations'
    ans = []
    for (c0i,d0i,v0i) in e1:
        for (c1i,d1i,v1i) in e2:
            ai = list(c0i)
            bi = list(d0i)
            ai.extend(c1i)
            bi.extend(d1i)
            vi = solve(v0i, v1i, var)
            ans.append((ai,bi,vi))
    print 'SimplifyITEeq input has {0} = {1} cases'.format(len(e1),len(e2))
    print 'SimplifyITEeq output has {0} cases'.format(len(ans))
    return (var, ans)

def others2saldef(varvall):
    "varvall is a list of (var,ans) as above; output it as sal definition"
    def ite2sal(val):
        first, ans = True, ""
        for (c,d,v) in val:
            sep = "ELSIF" if not first else "IF"
            first = False
            ans += "\n    {2} {0} AND {1} ".format(toSal(c,0),toSal(d,1),sep)
            ans += "\n    THEN {0}".format(expr2sal(v,flag = False))
        # Repeating last value in ELSE clause.....
        ans += "\n    ELSE {0} ENDIF".format(expr2sal(v,flag=False))
        return ans
    ans = ""
    if len(varvall) == 0:
        return ans
    ans += "\n  DEFINITION"
    first = True
    for (var,val) in varvall:
        sep = ";" if not first else ""
        first = False
        ans += "{1}\n   {0} = ".format(var,sep)
        ans += ite2sal(val)
    return ans
    
def replace(node, newnode, root):
    '''replace node by newnode and call simplify'''
    if node == root:	# I am the expr
        root = newnode
    else:
        parentnode = node.parentNode
        parentnode.replaceChild(newChild=newnode,oldChild=node)
    return root

def toSal(pn, flag):
    ans = ""
    first = True
    if len(pn) == 0:
        ans = 'TRUE'
    for i in pn:
        ans += ' AND ' if not first else ''
        first = False
        if flag == 0:
            ans += '(' + expr2sal(i, flag = False) + ')' # CHECK flag setting
        else:
            ans += 'NOT(' + expr2sal(i, flag = False) + ')'
    return ans

def createPlant(state, ceqns, oeqns, dom):
    "print the PLANT HSAL module"
    def occurs(var, node):
        ids = node.getElementsByTagName('identifier')
        for i in ids:
            if valueOf(i).strip() == var:
                return True
        if node.tagName == 'identifier' and valueOf(node).find(var) != -1:
            return True
        return False
    def applySubstitution(expr, mapping):
        for (var,val) in mapping:
            expr = applySubstitution1(expr, var, val)
        return expr
    def applySubstitution1(expr, var, val):
        ans = []
        for (ci,di,vi) in expr:
            if not occurs(var,vi):
                ans.append( (ci,di,vi) )
            else:
                for (ai,bi,wi) in val:
                    u1 = list( ci )
                    u1.extend( ai )
                    v1 = list( di )
                    v1.extend( bi )
                    ans.append( (u1,v1, applySubBase(vi,var,wi)) )
        return ans
    def applySubBase(node, var, val):
        expr = node.cloneNode(True)
        ids = expr.getElementsByTagName('identifier')
        for i in ids:
            varname = valueOf(i).strip()
            if varname == var:
                valuecopy = val.cloneNode(True)
                expr = replace(i, valuecopy, expr)
        return expr
    def applyOp(op, e1, e2):
        "multiply two conditional exprs"
        ans = []
        if valueOf(op).strip() == '*':
            for (p1,n1,v1) in e1:
                for (p2,n2,v2) in e2:
                    p12 = list(p1)
                    n12 = list(n1)
                    v12 = helper_create_app('BAPP',[op.cloneNode(True),v1.cloneNode(True),v2.cloneNode(True)])
                    p12.extend(p2)
                    n12.extend(n2)
                    ans.append((p12,n12,v12))
        else:
            assert False, 'No other operator supported'
        return ans
    def expr2cexpr2( val ):
        if val.tagName == 'BAPP':
            op = getArg(val, 1)
            a1 = getArg(val, 2)
            a2 = getArg(val, 3)
            e1 = expr2cexpr2( a1 )
            e2 = expr2cexpr2( a2 )
            return applyOp( op, e1, e2 )
        else:
            return expr2cexpr(val)
    def expr2cexpr( val ):
        "expr 2 conditional expr"
        ans = []
        if val.tagName != 'IF':
            return [([], [], val)]
        else: # val.tagName == 'IF':
            while val.tagName == 'IF':
                iteCond = getArg(val, 1)
                iteThen = getArg(val, 2)
                val = getArg(val, 3)
                ans.append( ([iteCond], [], iteThen) )
            ans.append( ( [], [iteCond], val ) )
        return ans
    def myproduct( vvl ):
        "vvl = list of (var, (p,n,v)-list). OUTPUT (p,n,(var,v)-list)"
        ans = []
        for (var,val) in vvl:
            tmp = []
            for (p,n,v) in val:
                tmp.append( (p,n,[(var,v)]) )
            ans.append(tmp)
        if len(ans) <= 1:
            return ans
        else:
            return myproductAux( ans[1:], ans[0] )
    def myproductAux( pnvvlll, pnvvll ):
        if len(pnvvlll) == 0:
            return pnvvll
        pnvvll2 = pnvvlll[0]
        ans = []
        for (p,n,vvl) in pnvvll2:
            for (p1,n1,vvl1) in pnvvll:
                x = list(p)
                y = list(n)
                x.extend(p1)
                y.extend(n1)
                z = list(vvl)
                z.extend(vvl1)
                ans.append( (x,y,z) )
        return myproductAux( pnvvlll[1:], ans )
    ans = "\n plant: MODULE = \n BEGIN"
    (bools,reals,ints,inputs,nonstates,vmap) = state
    for i in bools:
        ans += "\n  INPUT {0}: BOOLEAN".format(i)
    for i in ints:
        ans += "\n  INPUT {0}: NATURAL".format(i)
    for i in reals:
        if i in inputs:
            ans += "\n  INPUT {0}: REAL".format(i)
        else:
            ans += "\n  OUTPUT  {0}: REAL".format(i)
    ans  += "\n  INITIALIZATION"
    first = True
    for i in reals:
        initval = getInitialValue(vmap,i)
        if initval != None:
            sep = ";" if not(first) else ""
            first = False if first else first
            ans += "{2}\n\t {0} = {1}".format(i,initval,sep)
    # ASHISH: get init values from dom2 ????
    # first get conditional diff eqns ; then print
    # ans  += "\n  TRUE -->"
    ode = []
    for e in ceqns:
        lhs = getArg(e,1) 
        rhs = getArg(e,2) 
        (var,val) = (rhs,lhs) if rhs.tagName == 'der' else (lhs,rhs)
        name = valueOf(getArg(var,1)).strip()
        rhs =  expr2cexpr(val)
        ode.append( (name, rhs) )
        print 'ODE for {0} has {1} cases'.format(name,len(rhs))
    others = []
    for e in oeqns:
        lhs = getArg(e,1) 
        rhs = getArg(e,2) 
        e1 =  expr2cexpr2(lhs)
        e2 =  expr2cexpr2(rhs)
        others.append( (e1, e2) )
        print 'Other equation has {0} and {1} cases'.format(len(e1),len(e2))
        # print 'lhs = {0}'.format(daexmlPP.ppExpr(lhs))
        # print 'rhs = {0}'.format(daexmlPP.ppExpr(rhs))
        # print 'e1 = {0}'.format(e1)
        # print 'e2 = {0}'.format(e2)
    others = [ simplifyITEeq(e1,e2) for (e1,e2) in others ]
    # now I have the substitution in others; apply it to ode
    ans += others2saldef(others)
    newode = [(var,applySubstitution(val, others)) for (var,val) in ode]
    finalode = myproduct(newode)
    ans  += "\n  TRANSITION\n  ["
    first = True
    for (p,n,vvl) in finalode:
        sep = "\n  []" if not(first) else ""
        first = False
        ans += "{2}\n  {0} AND {1} -->".format(toSal(p,0),toSal(n,1),sep)
        ffirst = True
        for (var,val) in vvl:
            sep = ";" if not(ffirst) else ""
            ffirst = False if ffirst else ffirst
            ans += "{2}\n\t {0} = {1}".format(var+"dot'",expr2sal(val,flag=False),sep)
    ans += "\n  ]"
    ans += "\n END;\n"
    return ans
# -----------------------------------------------------------------

def createEventsFromPreds(preds, reals, inputs):
    "preds = list of (var,val-list) or ((bop,e1,e2), val-list)"
    "output formula that says that one event is generated at each time step on reals"
    ans,first = "", True
    for (e,vl) in preds.items():
        if isinstance(e,tuple):
            (bop,e1,e2) = e
            assert isinstance(e1,str) or isinstance(e1,unicode)
            assert isinstance(e2,str) or isinstance(e2,unicode)
            estr = e1 + "'" + bop + e2 + "'"
        else:
            assert isinstance(e,str) or isinstance(e,unicode), 'Error: Expecting str/unicode, found {0}'.format(type(e))
            estr = e + "'"
            if (e not in reals) or (e in inputs):
                continue
        for v in vl:
            sep = " OR" if not first else ""
            first = False
            ans += "{2} {0} = {1}".format(estr,str(v),sep)
    return ans
            

# -----------------------------------------------------------------
def convert2hsal(dom1, dom2):
    "dom1: DAE XML; dom2: original modelica XML; return HSal as string"
    def alpha_rename_aux(ans, bools):
        for i in bools:
            if i.find('.') is not -1:
                j = i.replace('.','_')
                ans = ans.replace(i, j)
        return ans
    def alpha_rename(ans, state):
        (bools,reals,ints,inputs,nonstates,vmap) = state
        ans = alpha_rename_aux(ans, bools)
        ans = alpha_rename_aux(ans, ints)
        ans = alpha_rename_aux(ans, reals)
        return ans
    # decide later if creating hsal XML or hsal string
    cstate = getIdentifiersIn(dom1,'continuousState')
    dstate = getIdentifiersIn(dom1,'discreteState')
    knownvars = dom1.getElementsByTagName('knownVariables')[0]
    varvals = knownvars.getElementsByTagName('variablevalue')
    if varvals != None and len(varvals) > 0:
        print 'ERROR: Unable to eliminate knownVariable equations'
        return -1
    Eqn = dom1.getElementsByTagName('equations')[0]
    eqns = getElementsByTagTagName(dom1, 'equations', 'equation')
    print 'Found {0} equations. Processing...'.format(len(eqns))
    var_details = getElementsByTagTagName(dom2, 'orderedVariables', 'variable')
    var_details2 = getElementsByTagTagName(dom2, 'knownVariables', 'variable')
    var_details.extend(var_details2)
    (discEqns,contEqns,oEqns) = classifyEqns(eqns,cstate,dstate)
    print 'Classified eqns into {0} discrete, {1} cont, {2} others'.format(len(discEqns),len(contEqns),len(oEqns))
    state = findState(Eqn,cstate,dstate,var_details)
    (bools,reals,ints,inputs,nonstates,vmap) = state
    print 'Found {0} bools, {1} reals, {2} ints'.format(len(bools),len(reals),len(ints))
    print 'Found {0} inputs, {1} non-states'.format(len(inputs),len(nonstates))
    # preds = getPredsInConds(contEqns)
    preds = getPredsInConds(eqns)
    print 'Found {0} preds'.format(len(preds))
    print preds
    ans0 = createEventsFromPreds(preds, reals, inputs)	# Should events on inputs be included?
    ans1 = createControl(state, discEqns, ans0, dom1)
    ans2 = createPlant(state, contEqns, oEqns, dom1)
    # replace varname.var -> varname_var
    ans = ans1 + ans2
    ans = alpha_rename(ans, state)
    return ans

def create_output_file(filename, hsalstr):
    def moveIfExists(filename):
        import shutil
        if os.path.isfile(filename):
            print "Output file {0} exists.".format(filename),
            print "Renaming old file to {0}.".format(filename+"~")
            shutil.move(filename, filename + "~")
    basename,ext = os.path.splitext(filename)
    basename += "Model"
    outfile = basename + ".hsal"
    moveIfExists(outfile)
    (dirname,basefilename) = os.path.split(basename)
    ansBEGIN = basefilename
    ansBEGIN += ": CONTEXT ="
    ansBEGIN += "\nBEGIN"
    ansEND = "\nEND"
    system = "\n\n system: MODULE = control || plant ;"
    with open(outfile, "w") as fp:
        print >> fp, '% Generated automatically by daexml2hsal'
        print >> fp, ansBEGIN
        print >> fp, hsalstr
        print >> fp, system
        print >> fp, ansEND
    print "Created file %s containing the HybridSAL representation" % outfile
    return 0

def printUsage():
    print '''
daexml2hsal -- a converter from differential algebraic equations to HybridSal

Usage: python daexml2hsal <daexml_file> <modelica_xmlfile>
    '''

def daexml2hsal(dom1, dom2, filename):
    global dom
    dom = dom1
    hsalstr = convert2hsal(dom1, dom2)
    create_output_file(filename, hsalstr)

def main():
    global dom
    if not len(sys.argv) == 3:
        printUsage()
        return -1
    basename,ext1 = os.path.splitext(sys.argv[1])
    basename,ext2 = os.path.splitext(sys.argv[2])
    if not(ext1 in ['.xml','.daexml','.dae_flat_xml'] and ext2 == '.xml'):
        print 'ERROR: Unknown files; expecting XML files'
        printUsage()
        return -1
    if not(os.path.isfile(sys.argv[1]) and os.path.isfile(sys.argv[2])):
        print 'ERROR: File does not exist'
        printUsage()
        return -1
    dom1 = xml.dom.minidom.parse(sys.argv[1])
    dom2 = xml.dom.minidom.parse(sys.argv[2])
    dom = dom1
    hsalstr = convert2hsal(dom1, dom2)
    create_output_file(sys.argv[1], hsalstr)
    return 0

if __name__ == "__main__":
    main()
