# Main file for creating cc_hra_verifier. Copied from hsalRA.py
import sys
import os
import os.path
import inspect
import subprocess

# adds the current folder (where this file resides) into the path
thisfile = os.path.abspath(inspect.getfile( inspect.currentframe() ))
folder = os.path.split( thisfile )[0]
relabsrootfolder = os.path.join(folder, '..', '..')
relabsrootfolder = os.path.realpath(os.path.abspath(relabsrootfolder))
relabsfolder = os.path.join(relabsrootfolder, 'src')
relabsfolder = os.path.realpath(os.path.abspath(relabsfolder))
ccfolder = os.path.realpath(os.path.abspath(folder))
modelicafolder = os.path.join(relabsrootfolder, 'modelica2hsal', 'src')
#print folder, relabsfolder
for i in [ccfolder, relabsfolder, modelicafolder]:
    if i not in sys.path:
        sys.path.insert(0, i)
os.environ['PATH'] += '{1}{0}{1}'.format(relabsrootfolder,os.path.pathsep)    # insert for jar file
# insert modelicafolder too later and then import modelica2hsal if needed later

import HSalRelAbsCons
import cybercomposition2hsal
import modelica2hsal
import modelica_slicer

#copying from install.py... will find sal here.
def findFile(basedir, filename, blacklist):
    """See if you can find filename in any directory in basedir"""
    for root, dirs, files in os.walk( basedir ):
        if filename in files:
            return os.path.join(root, filename)
        for i in blacklist:
            if i in dirs:
                dirs.remove(i)
    return None

def checkexe(filename, env_names, flags = None):
  for env_name in env_names:
    exepaths = os.environ[ env_name ].split(os.path.pathsep)
    for i in exepaths:
        exefile = os.path.join(i, filename)
        if os.path.exists(exefile):
            if flags == None:
                return exefile
            try:
                call_list = [ exefile ]
                call_list.extend( flags )
                ret_code = subprocess.call( call_list )
                return exefile
            except Exception, e:
                print 'Warning: File {0} found in PATH, but not executable.'.format(exefile)
                continue
  print 'WARNING: File {0} not found in PATH.'.format(filename)
  return None

def find_sal_exe():
    salinfbmc = 'sal-inf-bmc'
    salinfbmc_nexe = checkexe(salinfbmc, ['PATH'], flags = None)
    salinfbmc_exe = checkexe(salinfbmc, ['PATH'], flags = ['-V'])
    if salinfbmc_exe != None:
        print "Using {0}".format(salinfbmc_exe)
        return [ salinfbmc_exe ]
    iswin = sys.platform.startswith('win')	# is windows
    if not(iswin):	# not windows
        print "***SAL not found.  Download and install SAL.***"
        print "***Update PATH with location of sal-inf-bmc.***"
        return None
    cygwin = os.path.join('C:',os.path.sep,'cygwin')
    print 'Checking for cygwin at {0}'.format(cygwin)
    if os.path.isdir(cygwin):
        pass
    elif os.environ.has_key('CYGWIN_HOME'):
        cygwin = os.environ['CYGWIN_HOME']
        assert os.path.isdir(cygwin), 'CYGWIN_HOME is not a directory!!!'
    else:    
        print '***Unable to find cygwin; install cygwin and sal***'
        print '***If cygwin is not installed in the standard location c:/cygwin/, then set environment variable CYGWIN_HOME.***'
        return None
    print 'cygwin found at {0}'.format(cygwin)
    print 'searching for sal-inf-bmc...'
    if salinfbmc_nexe != None:
      salinfbmc = salinfbmc_nexe
    else:
      blacklist = ['zoneinfo','cache','locale','font','doc','include','examples','terminfo','man','lib']
      salinfbmc = findFile(cygwin, 'sal-inf-bmc', blacklist)
    if salinfbmc != None:
        print 'sal-inf-bmc found at {0}'.format(salinfbmc)
    elif os.environ.has_key('SAL_HOME'):
        salhome = os.environ['SAL_HOME']
        assert os.path.isdir(salhome), 'Env var SAL_HOME is not a directory!!!!'
        salinfbmc = os.path.join(salhome, 'bin', 'sal-inf-bmc')
        assert os.path.isfile(salinfbmc), 'SAL_HOME/bin/sal-inf-bmc NOT found!!!!'
    else:
        print '***Unable to find SAL; download and install from sal.csl.sri.com'
        print '***If installed in non-standard location, set ENV variable SAL_HOME'
        return None
    # now we have salinfbmc and cygwin both set...
    cygwinbash = os.path.join(cygwin, 'bin', 'bash.exe')
    assert os.path.isfile(cygwinbash), "ERROR: {0} not found".format(cygwinbash)
    return [cygwinbash, '-li', salinfbmc]

def get_prop_str( sal_file, prop_name ):
  '''sal_file = relevant file content as string, prop_name = string'''
  i = sal_file.find( prop_name )
  if i == -1:
    return 'Failed to get property string'
  i = sal_file.find( '|-', i )
  j = sal_file.find( ';', i )
  return sal_file[ i+2: j]

# ---------------------------------------------------------------------
# Operations on HybridSAL file -- operates on strings
# ---------------------------------------------------------------------
def hsal_file_to_str( hsalfilename ):
  f = open( hsalfilename, 'r' )
  hsal_model = f.read()
  f.close()
  return hsal_model

def get_props_from_hsal_file(hsal_model):
  '''get all (propertyName, moduleName) from the HybridSal file. Recall
     propertyName: THEOREM moduleName |- LTL_prop'''
  propList = []
  offset, index = 0, hsal_model.find("THEOREM")
  while index != -1:
    endindex = hsal_model.rfind( ':', 0, index )
    startindex = hsal_model.rfind( ';', 0, endindex )
    propName = hsal_model[startindex+1:endindex].strip()
    # Now get the moduleName
    vdashIndex = hsal_model.find( '|-', index )
    moduleName = hsal_model[index+7:vdashIndex].strip()
    propList.append( (propName, moduleName) )
    offset = vdashIndex + 1
    index = hsal_model.find("THEOREM", offset)
  return propList

def get_module_str_from_hsal_file(hsal_model, modulename):
  beginIndex = hsal_model.find( modulename + ': MODULE')
  endIndex = hsal_model.find( 'END;', beginIndex)
  module_str = hsal_model[ beginIndex:endIndex ]
  return module_str

def get_module_X_from_module_str(module_str, keyword):
  '''keyword = INPUT or OUTPUT,
     RECALL HSAL syntax -- keyword varname: typename
     return inputs-list or outputs-list, where each input/output
     is a (name, type) tuple'''
  ans = []
  index = module_str.find( keyword )
  while index != -1:
    endIndex = module_str.find( ':', index)
    varname = module_str[index+5:endIndex].strip()
    vartype = module_str[endIndex+1:endIndex+10].strip()
    ans.append( (varname, vartype) )
    index = module_str.find( keyword, endIndex )
  return ans

def get_module_io_from_hsal_str(hsal_str, modulename):
  module_str = get_module_str_from_hsal_file(hsal_str, modulename)
  inputs = get_module_X_from_module_str( module_str, 'INPUT')
  outputs = get_module_X_from_module_str( module_str, 'OUTPUT')
  return (inputs, outputs)
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
def printUsage():
    print '''
cc_modelica_hra_verifier: A Verifier for CyberComposition + 
   Modelica models; Uses HybridSal Relational Abstracter

Usage: python cc_modelica_hra_verifier.py <CC.xml> <Modelica.xml>  OR
       cc_modelica_hra_verifier.exe <CC.xml> <Modelica.xml>

Description: This will analyze all LTL properties in the CC.xml model, and
 create a file called CCResults.txt containing the analysis results.'''

def argCheck(args, printUsage):
    "args = sys.argv list"
    if not len(args) >= 3:
        printUsage()
        sys.exit(-1)
    if args[1].startswith('-') or args[2].startswith('-'):
        printUsage()
        sys.exit(-1)
    for i in range(1,3):
      filename = args[i]
      basename,ext = os.path.splitext(filename)
      if not(ext == '.xml'):
        print 'ERROR: Unknown extension {0}; expecting .xml'.format(ext)
        printUsage()
        sys.exit(-1)
      if not(os.path.isfile(filename)):
        print 'ERROR: File {0} does not exist'.format(filename)
        printUsage()
        sys.exit(-1)
    return (args[1], args[2])

def main():
    def getexe():
        folder = os.path.split(inspect.getfile( inspect.currentframe() ))[0]
        relabsfolder = os.path.join(folder, '..', '..', 'bin')
        relabsfolder = os.path.realpath(os.path.abspath(relabsfolder))
        return relabsfolder
    global dom
    (ccfilename, modfilename) = argCheck(sys.argv, printUsage)
    try:
        (basefilename, propNameList) = cybercomposition2hsal.cybercomposition2hsal(ccfilename, options = sys.argv[3:])
    except Exception, e:
        print e
        print 'ERROR: Unable to translate CyberComposition XML to HybridSal'
        return -1
    assert type(basefilename) == str, 'ERROR: cc2hsal return value type: string expected'
    hsalfile = basefilename + '.hsal'
    if not(os.path.isfile(hsalfile) and os.path.getsize(hsalfile) > 100):
        print 'ERROR: Unable to translate CyberComposition XML to HybridSal. Quitting.'
        return -1

    # Now run the modelica_slicer...

    # now I need to run hsal2hasal
    try:
        xmlfilename = HSalRelAbsCons.hsal2hxml(hsalfile)
    except Exception, e:
        print e
        print 'ERROR: Failed to parse generated HybridSal file. Syntax error in generated HybridSal file. Quitting.'
        return -1
    if not(type(xmlfilename) == str and os.path.isfile(xmlfilename) and os.path.getsize(xmlfilename) > 100):
        print 'ERROR: Failed to parse HybridSal file. Quitting.'
        return -1
    try:
        ans_prop_exists = HSalRelAbsCons.hxml2sal(xmlfilename, optarg=0, timearg=None, ptf=False)
    except Exception, e:
        print e
        print 'ERROR: Relational abstracter can not abstract this model. Quitting.'
        return -1
    if not isinstance(ans_prop_exists, tuple):
        print 'ERROR: Relational abstracter failed to abstract this model. Quitting.'
        return -1
    (ans, prop_exists) = ans_prop_exists
    if not(type(ans) == str and os.path.isfile(ans) and os.path.getsize(ans) > 100):
        print 'ERROR: Failed to abstract HybridSal model into a SAL model. Quitting.'
        return -1
    # iswin = sys.platform.startswith('win')
    # if pfilename != None:
    if prop_exists:
        salinfbmcexe = find_sal_exe()
        if salinfbmcexe == None:
            print 'ERROR: Failed to find sal-inf-bmc. Ensure SAL is installed.'
            return -1
        # change directory to where the sal file was created...
        #if os.environ.has_key('SALCONTEXTPATH'):
            #oldpath = os.environ['SALCONTEXTPATH']
        #else:
            #oldpath = '.'
        hsal_file_path = os.path.abspath(ans) 
        (basename,ext) = os.path.splitext(hsal_file_path)
        result_filename = basename + 'Result.txt'
        hsal_file_path = hsal_file_path.replace('\\', '/')
        hsal_file_path = hsal_file_path.replace('C:', '/cygdrive/c')
        try:
          f = open(result_filename, 'w')
        except Exception, e:
          print 'Failed to open file {0} for writing results'.format(result_filename)
          return -1
          #print 'Results will be displaced on stdout'
          #f = sys.stdout
        #hsal_file_path = hsal_file_path.replace('C:', '/c/')
        #os.environ['SALCONTEXTPATH'] = hsal_file_path + ':' + oldpath 
        #print 'SALCONTEXTPATH = ', os.environ['SALCONTEXTPATH']
        hsal_str = ''
        with open(hsalfile, 'r') as hsal_fp:
          old_pos = hsal_fp.tell()
          line_str = hsal_fp.readline()
          while line_str != '' and line_str.find('THEOREM') == -1:
            old_pos = hsal_fp.tell()
            line_str = hsal_fp.readline()
          if line_str != '':  # if there are properties
            hsal_fp.seek( old_pos )
            hsal_str = hsal_fp.read()
        for p1 in propNameList:
          print >> f, 'PropertyName: {0}'.format(p1)
          print >> f, 'PropertyStr: {0}'.format(get_prop_str(hsal_str,p1))
          f.flush()
          cmd = list(salinfbmcexe)
          cmd.extend(["-d", "10", hsal_file_path, p1])
          retCode = subprocess.call( cmd, env=os.environ, stdout=f)
          f.flush()
          if retCode != 0:
              print "sal-inf-bmc failed."
              return -1
          print >> f, '~~~~~~~~~~'
          f.flush()
        f.close()
        #print 'NOTE: Download and install SAL from sal.csl.sri.com'
    else:
        print 'No LTL properties were provided'
        print 'For verifying the model, add a property either in the Matlab model or in the translated SAL file directly'
        print 'Then, Use the command: sal-inf-bmc -d 4 <GeneratedSALFile> <propertyName added in generated SAL file>'
        return -1
    return 0

if __name__ == "__main__":
    ret_code = main()
    sys.exit(ret_code)

