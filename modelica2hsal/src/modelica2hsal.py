import sys
import os
import xml.dom.minidom
import ModelicaXML	# modelica -> dae
import ddae		# dae -> daexml
import daeXML		# daexml -> simplified daexml
import daexmlPP
import daexml2hsal	# daexml -> hsal

def printUsage():
    print '''
modelica2hsal -- a converter from Modelica to HybridSal

Usage: python modelica2hsal.py <modelica_file.xml> [<context_property.xml>] [--addTime]

Description: This will create a file called modelica_fileModel.hsal
    '''

def moveIfExists(filename):
    import shutil
    if os.path.isfile(filename):
        print "File %s exists." % filename,
        print "Renaming old file to %s." % filename+"~"
        shutil.move(filename, filename + "~")

def argCheck(args, printUsage):
    "args = sys.argv list"
    if not len(args) >= 2:
        printUsage()
        sys.exit(-1)
    if args[1].startswith('-'):
        printUsage()
        sys.exit(-1)
    filename = args[1]
    basename,ext = os.path.splitext(filename)
    if len(args) > 2 and not args[2].startswith('-'):
        pfilename = args[2]
        pbasename,pext = os.path.splitext(pfilename)
    else:
        pfilename = None
        pbasename,pext = None,'.xml'
    if not(ext == '.xml') or (not(pext == '.xml') and not(pext == '.json')):
        print 'ERROR: Unknown extension {0}; expecting .xml/.json'.format(ext)
        printUsage()
        sys.exit(-1)
    if not(os.path.isfile(filename)):
        print 'ERROR: File {0} does not exist'.format(filename)
        printUsage()
        sys.exit(-1)
    if (pfilename != None) and not(os.path.isfile(pfilename)):
        print 'ERROR: File {0} does not exist'.format(pfilename)
        printUsage()
        sys.exit(-1)
    return (filename, pfilename)

def main():
    global dom
    (filename, pfilename) = argCheck(sys.argv, printUsage)
    modelica2hsal(filename, pfilename, sys.argv[1:])

def modelica2hsal(filename, pfilename = None, options = []):
    basename,ext = os.path.splitext(filename)
    try:
        dom = xml.dom.minidom.parse(filename)
    except xml.parsers.expat.ExpatError, e:
        print 'Syntax Error: Input XML ', e 
        print 'Error: Input XML file is not well-formed...Quitting.'
        return -1
    except:
        print 'Error: Input XML file is not well-formed'
        print 'Quitting', sys.exc_info()[0]
        return -1
    dom2 = dom	# will be used later by daexml2hsal for variable information
    daefilename = basename + '.dae'
    moveIfExists(daefilename)
    print >> sys.stderr, 'Parsing Modelica XML file......'
    with open(daefilename,'w') as fp:
        ModelicaXML.HSalPPContext(dom, fp)   # create a .dae file
    print >> sys.stderr, 'Parsing complete. Created file {0}'.format(daefilename)
    # now parse the dae into daexml
    (dom,daexml) = ddae.dae2daexml(daefilename)
    os.remove(daefilename)	# this is .dae file
    daexmlfilename = basename + '.daexml'
    print >> sys.stderr, 'Created file {0}'.format(daexmlfilename)
    print >> sys.stderr, 'Trying to simplify the Modelica model...'
    try:
        dom1 = xml.dom.minidom.parse(daexmlfilename)
    except:
        print 'Model not supported: Unable to handle some expressions currently'
        sys.exit(-1)
    dom1 = daeXML.simplifydaexml(dom1,daexmlfilename)
    os.remove(daexmlfilename)	# this is .daexml file
    print >> sys.stderr, 'Finished simplification steps.'
    # daexmlPP.source_textPP(dom1)
    dom3 = None		# No property file given by default
    if pfilename != None and pfilename.rstrip().endswith('.xml'):
        print >> sys.stderr, 'Reading XML file containing context and property'
        try:
            dom3 = xml.dom.minidom.parse(pfilename)
        except xml.parsers.expat.ExpatError, e:
            print 'Syntax Error: Input XML ', e 
            print 'Error: Property XML file is not well-formed...Quitting.'
            return -1
        except:
            print 'Error: Property XML file is not well-formed'
            print 'Quitting', sys.exc_info()[0]
            return -1
        print >> sys.stderr, 'Finished reading context and property'
    elif pfilename != None and pfilename.rstrip().endswith('.json'):
        print >> sys.stderr, 'Reading JSON file containing context and property'
        try:
            import json
            with open(pfilename,'r') as fp:
                jsondata = fp.read()
                for i in ['\n','\r','\\']:
                    jsondata = jsondata.replace(i,'')
                dom3 = json.loads(jsondata)
                assert isinstance(dom3,dict),'ERROR: Expected dict in JSON file'
        except SyntaxError, e:
            print 'Syntax Error: Input JSON ', e 
            print 'Error: Property JSON file is not well-formed...Quitting.'
            return -1
        except:
            print 'Error: Unable to read property JSON file...Quitting.'
            return -1
    print >> sys.stderr, 'Creating HybridSal model....'
    outfile = daexml2hsal.daexml2hsal(dom1, dom2, daexmlfilename, dom3, options = options)
    print >> sys.stderr, 'Created HybridSal model.'
    return outfile

if __name__ == "__main__":
    main()

'''
	python ModelicaXML.py RCEngine.xml  > RCEngine.dae
	python ddae.py RCEngine.dae
	python daeXML.py RCEngine.daexml
	mv RCEngine.dae_flat_xml RCEngine1.daexml
	python daexmlPP.py RCEngine1.daexml > RCEngine1.dae
	python daexml2hsal.py RCEngine1.daexml RCEngine.xml
'''
