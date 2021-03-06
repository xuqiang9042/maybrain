# -*- coding: utf-8 -*-
"""
Created on Fri Apr 11 19:05:26 2014
Module for linking with the Allen brain atlas
@author: tim
"""

import maybrain.brainObjs as mbo

import csv
from os import path,rename,remove
import numpy as np
from scipy import stats
from matplotlib import pyplot as plt
from glob import glob

class allenBrain:
    """
    
    """
    def __init__(self, allenSubj, assocMat, delim=",",
                 spatialFile="atlas471_xyz_flip_xy.txt", nodesToExclude=[],
                 symmetrise=False, mirror=False, convertMNI=False):
        """
        This object contains two 'brain' network objects, one for the imaging data and
        one for the Allen data. Embedded functions make a comparison between the imaging
        and Allen data by pairing nodes between the two network objects.
        """
      
        self.subj = allenSubj
        self.fName = "SampleAnnot.csv"
        self.maFile = "MicroarrayExpression.csv"
        self.probeFile = "Probes.csv"

        # if symmetrise is true then regions are identified by the structure name,
        # if symmetrise is false, then regions are identified by the structural acronym
        # these refer to headers in the SampleAnnot.csv file
        if symmetrise:
            self.sLab = "structure_acronym"
        else:
            self.sLab = "structure_name"
       
        self.mirror = mirror
        if symmetrise and self.mirror:
            print "Please select either a symmetrised or mirrored graph, ignoring mirror=True"
            self.mirror = False
            
        # set up brain for expression data
        self.a = mbo.brainObj()
        
        node_counter = 0
      
        # import probe data
        f = open(path.join(self.subj, self.fName), "rb")        
        reader = csv.DictReader(f, delimiter=",", quotechar='"')
      
        self.headers = ['probe']
        self.sIDDict = {}
        
        ### deprecated code for removal ####
#        for l in reader:
#            n = int(l[self.sLab])
#            self.a.G.add_node(n)
#            self.a.G.node[n] = l
#            self.headers.append(l["structure_id"])
#        f.close()
        
        for l in reader:
           # n = int(l["structure_id"])
           sID = l[self.sLab]
           n = node_counter # GIVE NODES UNIQUE INCREMENTAL ID (across all subjects)
           if not self.a.G.has_node(n):
               self.a.G.add_node(n)
               self.a.G.node[n] = l
               self.a.G.node[n]['sID'] = sID # store the structure_acronym/structure_name for the node
               node_counter += 1
               # self.headers[subj].append(l["structure_id"])
               self.headers.append(sID) #STORE structure_acronym or structure_name depending on symmetrise
               
               if not sID in self.sIDDict.keys():
                   self.sIDDict[sID] = [n]
               else:
                   self.sIDDict[sID].append(n)
        f.close()
      
        if convertMNI:
            # convert location data for Allen brain from MNI space
             for n in self.a.G.nodes():
                 x = 45 - (float(self.a.G.node[n]['mni_x'])/2)
                 y = 63 + (float(self.a.G.node[n]['mni_y'])/2)
                 z = 36 + (float(self.a.G.node[n]['mni_z'])/2)
                 self.a.G.node[n]['xyz'] = (x,y,z)
        else:
            for n in self.a.G.nodes():
                x = float(self.a.G.node[n]['mni_x'])
                y = float(self.a.G.node[n]['mni_y'])
                z = float(self.a.G.node[n]['mni_z'])
                self.a.G.node[n]['xyz'] = (x,y,z)
        
        # copy hemisphere if required
        if self.mirror and len(self.a.G.nodes()) < 600:
            self.a.copyHemisphere()
            
        # set up brain with graph properties
        self.c = mbo.brainObj()
        self.c.importAdjFile(assocMat, delimiter=delim,
                             exclnodes=nodesToExclude)
        self.c.importSpatialInfo(spatialFile)
  
    def comparison(self):
        # set up dictionary to link nodes from probe data and graph
        # keys are the mri nodes and values are disctionaries containing two keys: 
        # key 1= allen, value= (n=id of closest allen node, d=distance to closest allen node)
        # key 2= mri, value= (n=id of closest other mri node, d=distance to closest mri node)

        nodeDictMRIs = {}
      
        for node in self.c.G.nodes():
            dOther = (None, 999.) # dummy length of 999
            dOwn = (None, 999.)
      
            for n in self.a.G.nodes():
                d = np.linalg.norm(np.array(self.c.G.node[node]['xyz'] - np.array(self.a.G.node[n]['xyz'])))
                if d < dOther[1]:
                    dOther = (n,d)
          
            for n in [v for v in self.c.G.nodes() if not v==node]:
                d = np.linalg.norm(np.array(self.c.G.node[node]['xyz'] - np.array(self.c.G.node[n]['xyz'])))
                if d < dOwn[1]:
                    dOwn = (n,d)
            nodeDictMRIs[node] = {"allen":dOther, "MRIs":dOwn}
      
        # set up dictionary to link nodes from probe data and graph
        nodeDictAllen = {}
        for node in self.a.G.nodes():
            dOther = (None, 999.)
            dOwn = (None, 999.)
          
            for n in self.c.G.nodes():
                d = np.linalg.norm(np.array(self.a.G.node[node]['xyz'] - np.array(self.c.G.node[n]['xyz'])))
                if d < dOther[1]:
                    dOther = (n,d)
          
            for n in [v for v in self.a.G.nodes() if not v==node]:
                d = np.linalg.norm(np.array(self.a.G.node[node]['xyz'] - np.array(self.a.G.node[n]['xyz'])))
                if d < dOwn[1]:
                    dOwn = (n,d)
            nodeDictAllen[node] = {"allen":dOwn, "MRIs":dOther}
      
        nodePairs = []
        # for each MRI node
        for node in nodeDictMRIs.keys():
            # find closest allen node 'n'
            n = nodeDictMRIs[node]['allen'][0]
            self.c.G.node[node]['pair'] = n
            self.a.G.node[n]['pair'] = node
            nodePairs.append((node,n))
            # if there is no other MRI node closer to the current MRI region 
            # if nodeDictMRIs[node]['allen'][1] < nodeDictMRIs[node]['MRIs'][1]:
            # if there is also no other MRI node closer to this allen region then match
            #     n = nodeDictMRIs[node]['allen'][0]
            #     if nodeDictAllen[n]['MRIs'][0] == node:
            #         self.c.G.node[node]['pair'] = n
            #         self.a.G.node[n]['pair'] = node
            #         nodePairs.append((node,n))
            #     else:
            # if there is another MRI node closer to this allen region then delete current regions (and do not match it)
            #         self.c.G.remove_node(node)
            # else:
            #     self.c.G.remove_node(node)
      
        for node in self.a.G.nodes():
            if not 'pair' in self.a.G.node[node].keys():
                self.a.G.remove_node(node)             
                  
    def doPlot(self):
        self.a.importSkull("/usr/share/data/fsl-mni152-templates/MNI152_T1_2mm_brain.nii.gz")
        p = mbo.plotObj()
        p.plotSkull(self.a, contourVals = [3000,9000])
        p.plotBrainCoords(self.c, nodes =  self.c.G.nodes(),
                                     col=(1,0,0), sizeList=5)
        p.plotBrainCoord(self.a, nodes = self.a.G.nodes(),
                                     col=(0,0,1), sizeList=5)
        self.saveFig()
                                    
    def probeData(self, propDict, graphMetric="gm", nodeList=None, plot=False,
                  probeList=[], probeNumbers=[], sigVal=1.0, T=False):
        '''
        
        '''
        self.gm=graphMetric
        self.sigVal=sigVal
      
        probes = open(path.join(self.subj,"Probes.csv"), "rb")
        probeReader = csv.DictReader(probes, delimiter=",",
                                     quotechar='"')
        self.probeDict = {l['probe_id']:[l['gene_symbol'], l['gene_name']] for l in probeReader}
        if probeList:
            probeNumbers = []
            for p in probeList:
                probeNumbers.extend([v for v in self.probeDict.keys() if any([p in self.probeDict[v][1], p in self.probeDict[v][0]])])
            print " ".join(["Probe numbers:", ' '.join(probeNumbers)])
      
        else:
            probeNumbers = None
      
        self.outFile = path.join(self.subj, self.gm+'.txt')
        print "Saving data in:"+self.outFile
        if path.exists(self.outFile):
            rename(self.outFile, self.outFile+'.old')
        f = open(self.outFile,"w")
        f.writelines(','.join(['probe_id', 'gene_name', 'r','p\n']))
        f.close()

        self.propDict = propDict
                              
        if nodeList:
            for node in self.c.G.nodes():
                if not node in nodeList:
                    self.a.G.remove_node(self.c.G.node[node]['pair'])
                    self.c.G.remove_node(node)
      
        # import probe data
        f = open(path.join(self.subj, self.maFile), "rb")
        reader = csv.DictReader(f, delimiter=",",
                                fieldnames=self.headers,
                                quotechar='"')
      
        for l in reader:
            if T:
                self.probeSubT(l, plot, probeNumbers)
            else:
                self.probeSub(l, plot, probeNumbers)
        f.close()
       
    def writeXMatrix(self, outFile="Xmatrix.csv", probeNumbers=None, tempMatName="tempMat.txt", sd=False, sdFile="NodesSd.txt"):
       # get all probes if otherwise unspecified
       if not probeNumbers:
           f = open(path.join(self.subj, self.probeFile))
           reader = csv.DictReader(f, delimiter=",", quotechar='"')
           probeNumbers = [l['probe_id'] for l in reader]
           del(reader)
           f.close()  
  
       # set up out file
       out = open(self.subj+outFile, "wb")
       headers = ["Gene"]
       headers.extend([str(v) for v in self.c.G.nodes()])
       writer = csv.DictWriter(out, fieldnames = headers, delimiter=" ")
       writer.writeheader()
      
       # set up matrix
       y = len(probeNumbers)
       z = len(self.c.G.nodes())
       sT = np.max([len(self.sIDDict.values())]) # max numbers of nodes for any region
       
       probeMat = np.memmap(tempMatName,
                            dtype="float64",
                            mode="w+",
                            shape=(y,z,sT))
                           
       # set up gene list
       geneFlag = True
       pFile = open(path.join(self.subj, self.probeFile))
       pReader = csv.DictReader(pFile, delimiter=",", quotechar='"')
       pDict = {l['probe_id']:l['gene_symbol'] for l in pReader}
       geneList = pDict.values()
       set(geneList)
       geneList = {gene:[] for gene in geneList}
       
       sIDList = [v for v in self.headers if not v=='probe']
       sIDList = set(sIDList)
       
       # get the corresponding node names in the MRI graph
       # cNodes is a dict whose keys are all the MRI nodes and values are the matched alen nodes
       #### PV modified line below which constructed cNodes by looping through allen nodes
       # but with PV's lax matching criteria several mri nodes can be matched to same allen node
       # the mri pair of these allen nodes gets overwritten in self.a.G.nodes and so not all mri nodes will appear 
       # as pairs of allen nodes in this dict... need to look up pairs in self.c.G.nodes instead, where
       # each mri node is matched to an allen region
       # cNodes = {str(self.a.G.node[v]['pair']):v for v in self.a.G.nodes()}
       
       cNodes = {str(v):self.c.G.node[v]['pair'] for v in self.c.G.nodes()}
       
       # assign values to matrix
       print(str(self.subj))
       print('\n')
       # Generate custom fieldnames list for DictReader which doesn't rely on structure_id
       # *************************************
       fieldnames_pv = ['probe']
       myNodeDict = {}
       tempHeaders = self.headers
       tempHeaders.remove('probe')

       for p,q in enumerate(self.headers):
           myNodeDict[p] = q
           fieldnames_pv.append(str(p))   #####
       # *************************************

       # import probe data
       f = open(path.join(self.subj, self.maFile), "rb")
       reader = csv.DictReader(f, delimiter=",",
                               fieldnames=fieldnames_pv,
                               quotechar='"')
       y = 0
       for l in reader:
           probe = l['probe']
           if probe in probeNumbers:
               # assign probe values to sample numbers
               for z,cNode in enumerate(self.c.G.nodes()):
                   aNode = cNodes[str(cNode)]
                   # *************************************
                   # Find structure_acronym corresponding to the matched allen node
                   acronym = self.a.G.node[aNode][self.sLab]
                   # Initialise list for summing expression values for allen nodes with same structure_acronym
                   totalExpression = []
                   # Loop over allen nodes to find all those with the correct acronym for the current MRI node
                   # and add their expression values to the list for averaging
                   s=0
                   for ID, struct_ac in myNodeDict.iteritems():
                       if struct_ac == acronym:
                           # print(ID, struct_ac, l[str(ID)])
                           # print('\n')
                           # if l[str(ID)]:
                           totalExpression.append(float(l[str(ID)]))
                           probeMat[y,z,s] = float(l[str(ID)])
                           s+=1
                           
               if geneFlag:
                   geneList[pDict[probe]].append(y)  # records the position of the probe in a dictionary with genes as a key
               y+=1
       f.close()
       del(reader)

       # get values to normalise expression levels for each probe within subject
       for y in range(probeMat.shape[0]):
           # create a masked array removing the 0. values
           subjMat = np.ma.array(probeMat[y,:,sT:sT],
                                 mask=probeMat[y,:,sT:sT]==0.,
                                 dtype="float64")

           subjMat = (subjMat - np.mean(np.ma.array(subjMat, mask=subjMat==0.))) / np.std(np.ma.array(subjMat, mask=subjMat==0.))
           probeMat[y,:,sT:sT] = subjMat

       geneFlag=False
      
       # collapse across subjects and probes by gene
       geneNames = geneList.keys()
       geneNames.sort() # sort in to alphabetical order
       
       # collapse across nodes within regions (averaging across all subjects)
       # probeMat = np.mean(np.ma.array(probeMat, mask=probeMat==0.), axis=3) # this would work, but runs in to memory problems
       sh = probeMat.shape
       probeMatTemp = np.memmap("probeMatTemp.txt", mode="w+", dtype="float64", shape=sh[:2])

       # write out the standard deviation for each probe if specified
       if sd:
           sdOut = open(sdFile, "wb")
           sdOut.writelines("Probe Node sd\n")
       for y in range(sh[0]):
           for z in range(sh[1]):
               probeMatTemp[y,z] = np.mean(np.ma.array(probeMat[y,z], mask=probeMat[y,z]==0.)) # mask out unused values, ie where there are less than the maximum number of homolous nodes in a structural region
               if sd:
                   std = np.std(np.ma.array(probeMat[y,z], mask=probeMat[y,z]==0.))
                   sdOut.writelines(' '.join([str(int(probeNumbers[y])), str(self.c.G.nodes()[z]), "{:2.5f}".format(std)])+'\n')
       if sd:
           sdOut.close()
       
       # reassign the probe matrix and delete temporary memory-mapped file
       probeMat = probeMatTemp
       del(probeMatTemp)
       remove(tempMatName)
       
       for g,gene in enumerate(geneNames):
           if (geneList[gene]):
               x = probeMat.shape[1] # number of nodes
               y = len(geneList[gene]) # number of probes
                              
               geneMat = np.zeros(shape=(x,y), dtype="float64")
              
               for n,p in enumerate(geneList[gene]): # nb: p is the position of the probe recorded above
                   geneMat[:,n] = probeMat[p,:]
                              
               self.geneMat = geneMat
               meanGene = np.mean(np.ma.array(geneMat, mask=np.isnan(geneMat)), axis=1) # collapse values across probes for each gene
              
               outDict = dict(zip([str(v) for v in self.c.G.nodes()], ["{:10.20f}".format(v) for v in meanGene]))
               outDict["Gene"] = gene
               writer.writerow(outDict)
      
       self.geneList = geneList
       self.probeMat = probeMat
       out.close()
       remove("probeMatTemp.txt") # delete memory map file
       
    def probeSub(self, l, plot, probeNumbers=None):
        probe = l['probe']
        if probeNumbers:
            if probe in probeNumbers:
                # assign probe values to sample numbers
                for node in self.a.G.nodes():
                    sID = self.a.G.node[node][self.sLab]
                    if l[sID]:
                        self.a.G.node[node][probe] = l[sID]
                    else:
                        self.a.G.node[node][probe] = None
              
                aa = np.zeros((len(self.c.G.nodes()),3))
                
                for n,cnode in enumerate(self.c.G.nodes()):
                    node = self.c.G.node[cnode]['pair']
                    if self.propDict[self.a.G.node[node]['pair']]:
                        aa[n,0] = self.a.G.node[node][probe]
                        aa[n,1] = self.propDict[cnode]
                        aa[n,2] = cnode
                    else:
                        aa[n,:] = [np.nan, np.nan, np.nan]
              
                aa = aa[~np.isnan(aa)]
                aa.shape = (len(aa)/3,3)
                
                r,p = stats.pearsonr(aa[:,0], aa[:,1])
              
                if p < self.sigVal:
                    print probe
                    # plot graph
                    out = open(self.outFile, "a")
                    out.writelines(','.join([str(v) for v in [probe, '"'+self.probeDict[probe][1]+'"', r, p]])+'\n')
                    out.close()
                    if plot:
                        plt.scatter(aa[:,1], aa[:,0])
                        plt.savefig(self.outFile.replace('.txt',probe+'.png'), dpi=300)
                        plt.close()
                  
                    # save data
                    print "Saving data in :"+self.outFile.replace('.txt', probe+self.gm+'.txt')
                    datFile = open(self.outFile.replace('.txt', probe+self.gm+'.txt'), "wb")
                    datFile.writelines(' '.join([probe, self.gm, "node", "subj"])+'\n')
                    datFile.writelines('\n'.join([' '.join([str(aa[n,0]), str(aa[n,1]), str(aa[n,2]), self.subj]) for n in range(len(aa[:,1]))]))
                    datFile.close()
        else:
            pass
  
    def probeSubT(self, l, plot, probeNumbers=None):
        '''
        l is a line from the probe file.
        The purpose of this function is to write thresholded data to a datafile
        eg for use in ANOVA
        '''
        probe = l['probe']
        datFile = None
        if probeNumbers:
            if probe in probeNumbers:
                # assign probe values to sample numbers
                for node in self.a.G.nodes():
                    if l[str(node)]:
                        self.a.G.node[node][probe] = l[str(node)]
                    else:
                        self.a.G.node[node][probe] = None
                                    
                    outDict = {probe:probe, 'subj':self.subj}
                    for p in self.propDict.keys():
                        outDict[p] = self.propDict[p]
                  
                    if not datFile:
                        headers = [probe, "subj"]
                        gmSubjs = self.propDict[self.probeDict.keys()[0]].keys()
                        gmSubjs.sort()
                        headers.extend(gmSubjs)

                        datFile = open(self.outFile.replace('.txt', probe+self.gm+'.txt'), "wb")
                        writer = csv.DictWriter(datFile, fieldnames=headers, delimiter=" ")
                        writer.writeheader()
                      
                    writer.writerow(outDict)
      
    def norm(self,x):
        xMin = np.min(x)
        xMax = np.max(x)
      
        x = np.array((x)) - xMin
        x = (x/xMax) * 20
        return([v for v in x])

class multiSubj:
    """
    This object contains two 'brain' network objects, one for the imaging data and
    one for the Allen data. Embedded functions make a comparison between the imaging
    and Allen data by pairing nodes between the two network objects.
    """
    def __init__(self, assocMat, nodesToExclude=[], delim=" ",
                 subjList=None, spatialFile="parcel_500.txt", symmetrise=False,
                 convertMNI=False, mirror=True):
        if subjList:
            self.subjList = subjList
        else:
            self.subjList = [v for v in glob("17823*") if path.isdir(v)]
           
        self.fName = "SampleAnnot.csv"
        self.maFile = "MicroarrayExpression.csv"
        self.probeFile = "Probes.csv"
        self.mirror=mirror
        
        # if symmetrise is true then regions are identified by the structure name,
        # if symmetrise is false, then regions are identified by the structural acronym
        # these refer to headers in the SampleAnnot.csv file
        if symmetrise:
            self.sLab = "structure_acronym"
        else:
            self.sLab = "structure_name"
        
        # set up brain for expression data
        self.a = mbo.brainObj()
       
        node_counter = 0

        self.headers={}
        self.sIDDict = {} # dictionary storing the list of nodes for each structural ID by subject - for use later in averaging across all subjects
        for subj in self.subjList:
            self.sIDDict[subj] = {}
            # import probe data
            f = open(path.join(subj, self.fName), "rb")        
            reader = csv.DictReader(f, delimiter=",", quotechar='"')
           
            self.headers[subj] = ['probe']
            for l in reader:
                # n = int(l["structure_id"])
                sID = l[self.sLab]
                n = node_counter # GIVE NODES UNIQUE INCREMENTAL ID (across all subjects)
                if not self.a.G.has_node(n):
                    self.a.G.add_node(n)
                    self.a.G.node[n] = l
                    self.a.G.node[n]['sID'] = sID # store the structure_acronym/structure_name for the node
                    node_counter += 1
                    # self.headers[subj].append(l["structure_id"])
                    self.headers[subj].append(sID) #STORE structure_acronym or structure_name depending on symmetrise
                    
                    if not sID in self.sIDDict[subj].keys():
                        self.sIDDict[subj][sID] = [n]
                    else:
                        self.sIDDict[subj][sID].append(n)

            f.close()
            
            if convertMNI:
                # convert location data for Allen brain from MNI space
                 for n in self.a.G.nodes():
                     x = 45 - (float(self.a.G.node[n]['mni_x'])/2)
                     y = 63 + (float(self.a.G.node[n]['mni_y'])/2)
                     z = 36 + (float(self.a.G.node[n]['mni_z'])/2)
                     self.a.G.node[n]['xyz'] = (x,y,z)
            else:
                for n in self.a.G.nodes():
                    x = float(self.a.G.node[n]['mni_x'])
                    y = float(self.a.G.node[n]['mni_y'])
                    z = float(self.a.G.node[n]['mni_z'])
                    self.a.G.node[n]['xyz'] = (x,y,z)
            
            if self.mirror and len(self.a.G.nodes()) < 600:
                self.a.copyHemisphere()

        #    f.write('%s, %s, %s, %s \n' % (str(n), str(self.a.G.node[n]['xyz'][0]),str(self.a.G.node[n]['xyz'][1]),str(self.a.G.node[n]['xyz'][2])))
        #f.close()
       
        # set up brain with graph properties
        self.c = mbo.brainObj()
        self.c.importAdjFile(assocMat, delimiter=delim, exclnodes=nodesToExclude)
        self.c.importSpatialInfo(spatialFile)

    def comparison(self):
        """
        set up dictionary to link nodes from probe data and graph
        keys are the mri nodes and values are dictionaries containing two keys: 
        key 1= allen, value= (n=id of closest allen node, d=distance to closest allen node)
        key 2= mri, value= (n=id of closest other mri node, d=distance to closest mri node)
        """
        nodeDictMRIs = {}
       
        for node in self.c.G.nodes():
            dOther = (None, 999.) # dummy length of 999
            dOwn = (None, 999.)
       
            for n in self.a.G.nodes():
                d = np.linalg.norm(np.array(self.c.G.node[node]['xyz'] - np.array(self.a.G.node[n]['xyz'])))
                if d < dOther[1]:
                    dOther = (n,d)
           
            for n in [v for v in self.c.G.nodes() if not v==node]:
                d = np.linalg.norm(np.array(self.c.G.node[node]['xyz'] - np.array(self.c.G.node[n]['xyz'])))
                if d < dOwn[1]:
                    dOwn = (n,d)
            nodeDictMRIs[node] = {"allen":dOther, "MRIs":dOwn}
       
        # set up dictionary to link nodes from probe data and graph
        nodeDictAllen = {}
        for node in self.a.G.nodes():
            dOther = (None, 999.)
            dOwn = (None, 999.)
           
            for n in self.c.G.nodes():
                d = np.linalg.norm(np.array(self.a.G.node[node]['xyz'] - np.array(self.c.G.node[n]['xyz'])))
                if d < dOther[1]:
                    dOther = (n,d)
           
            for n in [v for v in self.a.G.nodes() if not v==node]:
                d = np.linalg.norm(np.array(self.a.G.node[node]['xyz'] - np.array(self.a.G.node[n]['xyz'])))
                if d < dOwn[1]:
                    dOwn = (n,d)
            nodeDictAllen[node] = {"allen":dOwn, "MRIs":dOther}
       
        nodePairs = []
        # for each MRI node
        for node in nodeDictMRIs.keys():
            # find closest allen node 'n'
            n = nodeDictMRIs[node]['allen'][0]
            self.c.G.node[node]['pair'] = n
            self.a.G.node[n]['pair'] = node
            nodePairs.append((node,n))
            # if there is no other MRI node closer to the current MRI region 
            # if nodeDictMRIs[node]['allen'][1] < nodeDictMRIs[node]['MRIs'][1]:
            # if there is also no other MRI node closer to this allen region then match
            #     n = nodeDictMRIs[node]['allen'][0]
            #     if nodeDictAllen[n]['MRIs'][0] == node:
            #         self.c.G.node[node]['pair'] = n
            #         self.a.G.node[n]['pair'] = node
            #         nodePairs.append((node,n))
            #     else:
            # if there is another MRI node closer to this allen region then delete current regions (and do not match it)
            #         self.c.G.remove_node(node)
            # else:
            #     self.c.G.remove_node(node)
       
        for node in self.a.G.nodes():
            if not 'pair' in self.a.G.node[node].keys():
                self.a.G.remove_node(node)

    def comparisonAveraged(self):
        """
        This function should generate sets of nodes in the imaging data associated
        with single nodes in the Allen data, ie all the closest imaging data nodes will
        be associated with any specific Allen node.
        """
        for n in self.a.G.nodes():
            self.a.G.node[n]['pairNodes'] = []
        
        # iterate through imaging nodes to find closes Allen node
        for node in self.c.G.nodes():
            dOther = (None, 999.) # dummy length of 999
       
            for n in self.a.G.nodes():
                d = np.linalg.norm(np.array(self.c.G.node[node]['xyz'] - np.array(self.a.G.node[n]['xyz'])))
                if d < dOther[1]:
                    dOther = (n,d)
                    
            self.a.G.node[dOther[0]]['pairNodes'].append(node)
       
        for node in self.a.G.nodes():
            if not self.a.G.node[node]['pairNodes']:
                self.a.G.remove_node(node)

    def probeData(self, probeNumbers=[], meanVals=True):
        """
        If meanVals is specified, this takes the mean probe value across subjects
        """
        for subj in self.subjList:
            # import probe data
            f = open(path.join(subj, self.maFile), "rb")
            reader = csv.DictReader(f, delimiter=",",
                                    fieldnames=self.headers[subj],
                                    quotechar='"')
            for l in reader:
                probe = l['probe']
                if probe in probeNumbers:
                    # assign probe values to sample numbers
                    for cnode in self.c.G.nodes():
                        node = self.c.G.node[cnode]['pair']
                        sID = self.a.G.node[node][self.sLab]
                        if not probe in self.a.G.node[node].keys():
                            self.a.G.node[node][probe] = {}
                           
                        if sID in l.keys():
                            self.a.G.node[node][probe][subj] = l[sID]
            f.close()
            del(reader)
        # self.a.G.nodes is a dict containing every UNIQUE structure id (across all subjects)
        if meanVals:
            for n in self.a.G.nodes():
                for probe in probeNumbers:
                    self.a.G.node[n][probe] = np.mean([float(v) for v in self.a.G.node[n][probe].values()])
               
    def writeXMatrix(self, outFile="Xmatrix.csv", probeNumbers=None, tempMatName="tempMat.txt", sd=False, sdFile="NodesSd.txt"):
        # get all probes if otherwise unspecified
        if not probeNumbers:
            f = open(path.join(self.subjList[0], self.probeFile))
            reader = csv.DictReader(f, delimiter=",", quotechar='"')
            probeNumbers = [l['probe_id'] for l in reader]
            del(reader)
            f.close()  
   
        # set up out file
        out = open(outFile, "wb")
        headers = ["Gene"]
        headers.extend([str(v) for v in self.c.G.nodes()])
        writer = csv.DictWriter(out, fieldnames = headers, delimiter=" ")
        writer.writeheader()
       
        # set up matrix
        x = len(self.subjList)
        y = len(probeNumbers)
        z = len(self.c.G.nodes())
        sT = np.max([np.max([len(v) for v in self.sIDDict[subj].values()]) for subj in self.sIDDict.keys()]) # max numbers of nodes for any region
        
        probeMat = np.memmap(tempMatName,
                             dtype="float64",
                             mode="w+",
                             shape=(y,z,sT*x))
                            
        # set up gene list
        geneFlag = True
        pFile = open(path.join(self.subjList[0], self.probeFile))
        pReader = csv.DictReader(pFile, delimiter=",", quotechar='"')
        pDict = {l['probe_id']:l['gene_symbol'] for l in pReader}
        geneList = pDict.values()
        set(geneList)
        geneList = {gene:[] for gene in geneList}
        
        sIDList = []
        for subj in self.subjList:
            sIDList.extend([v for v in self.headers[subj] if not v=='probe'])
        sIDList = set(sIDList)
        
        # get the corresponding node names in the MRI graph
        # cNodes is a dict whose keys are all the MRI nodes and values are the matched alen nodes
        #### PV modified line below which constructed cNodes by looping through allen nodes
        # but with PV's lax matching criteria several mri nodes can be matched to same allen node
        # the mri pair of these allen nodes gets overwritten in self.a.G.nodes and so not all mri nodes will appear 
        # as pairs of allen nodes in this dict... need to look up pairs in self.c.G.nodes instead, where
        # each mri node is matched to an allen region
        # cNodes = {str(self.a.G.node[v]['pair']):v for v in self.a.G.nodes()}
        
        cNodes = {str(v):self.c.G.node[v]['pair'] for v in self.c.G.nodes()}
        
        # assign values to matrix
        for x,subj in enumerate(self.subjList):
            print(str(subj))
            print('\n')
            # Generate custom fieldnames list for DictReader which doesn't rely on structure_id
            # *************************************
            fieldnames_pv = ['probe']
            myNodeDict = {}
            tempHeaders = self.headers[subj]
            tempHeaders.remove('probe')

            for p,q in enumerate(self.headers[subj]):
                myNodeDict[p] = q
                fieldnames_pv.append(str(p))   #####
            # *************************************

            # import probe data
            f = open(path.join(subj, self.maFile), "rb")
            reader = csv.DictReader(f, delimiter=",",
                                    fieldnames=fieldnames_pv,
                                    quotechar='"')
            y = 0
            for l in reader:
                probe = l['probe']
                if probe in probeNumbers:
                    # assign probe values to sample numbers
                    for z,cNode in enumerate(self.c.G.nodes()):
                        aNode = cNodes[str(cNode)]
                        # *************************************
                        # Find structure_acronym corresponding to the matched allen node
                        acronym = self.a.G.node[aNode][self.sLab]
                        # Initialise list for summing expression values for allen nodes with same structure_acronym
                        totalExpression = []
                        # Loop over allen nodes to find all those with the correct acronym for the current MRI node
                        # and add their expression values to the list for averaging
                        s=0
                        for ID, struct_ac in myNodeDict.iteritems():
                            if struct_ac == acronym:
                                # print(ID, struct_ac, l[str(ID)])
                                # print('\n')
                                # if l[str(ID)]:
                                totalExpression.append(float(l[str(ID)]))
                                probeMat[y,z,sT*x + s] = float(l[str(ID)])
                                s+=1
                                
                    if geneFlag:
                        geneList[pDict[probe]].append(y)  # records the position of the probe in a dictionary with genes as a key
                    y+=1
            f.close()
            del(reader)

            # get values to normalise expression levels for each probe within subject
            for y in range(probeMat.shape[0]):
                # create a masked array removing the 0. values
                subjMat = np.ma.array(probeMat[y,:,sT*x:sT*x+sT],
                                      mask=probeMat[y,:,sT*x:sT*x+sT]==0.,
                                      dtype="float64")

                subjMat = (subjMat - np.mean(np.ma.array(subjMat, mask=subjMat==0.))) / np.std(np.ma.array(subjMat, mask=subjMat==0.))
                probeMat[y,:,sT*x:sT*x+sT] = subjMat

            geneFlag=False
       
        # collapse across subjects and probes by gene
        geneNames = geneList.keys()
        geneNames.sort() # sort in to alphabetical order
        
        # collapse across nodes within regions (averaging across all subjects)
#        probeMat = np.mean(np.ma.array(probeMat, mask=probeMat==0.), axis=3) # this would work, but runs in to memory problems
        sh = probeMat.shape
        probeMatTemp = np.memmap("probeMatTemp.txt", mode="w+", dtype="float64", shape=sh[:2])

        # write out the standard deviation for each probe if specified
        if sd:
            sdOut = open(sdFile, "wb")
            sdOut.writelines("Probe Node sd\n")
            
        for y in range(sh[0]):
            for z in range(sh[1]):
                probeMatTemp[y,z] = np.mean(np.ma.array(probeMat[y,z], mask=probeMat[y,z]==0.)) # mask out unused values, ie where there are less than the maximum number of homolous nodes in a structural region
                if sd:
                    std = np.std(np.ma.array(probeMat[y,z], mask=probeMat[y,z]==0.))
                    sdOut.writelines(' '.join([str(int(probeNumbers[y])), str(self.c.G.nodes()[z]), "{:2.5f}".format(float(std))])+'\n')

                        
        if sd:
            sdOut.close()
                
        # reassign the probe matrix and delete temporary memory-mapped file
        probeMat = probeMatTemp
        del(probeMatTemp)
        remove(tempMatName)
        
        for g,gene in enumerate(geneNames):
            if (geneList[gene]):
                x = probeMat.shape[1] # number of nodes
                y = len(geneList[gene]) # number of probes
                               
                geneMat = np.zeros(shape=(x,y), dtype="float64")
               
                for n,p in enumerate(geneList[gene]): # nb: p is the position of the probe recorded above
                    geneMat[:,n] = probeMat[p,:]
                               
                self.geneMat = geneMat
                meanGene = np.mean(np.ma.array(geneMat, mask=np.isnan(geneMat)), axis=1) # collapse values across probes for each gene
               
                outDict = dict(zip([str(v) for v in self.c.G.nodes()], ["{:10.20f}".format(v) for v in meanGene]))
                outDict["Gene"] = gene
                writer.writerow(outDict)
       
        self.geneList = geneList
        self.probeMat = probeMat
        out.close()
        remove("probeMatTemp.txt") # delete memory map file
   
    def writeYMatrixGroup(self, metricDict, subj="Control", outFile="YmatrixGroup.csv"):
        '''
        Collates metrics in to a matrix for use in partial least squares analysis.
        Note, the metricDict contains the metric name as a key and filename as
        the value. Takes group level measures
        '''
        out = open(outFile, "wb")
        headers = ["Metric"]
        headers.extend([str(v) for v in self.c.G.nodes()])
        writer = csv.DictWriter(out, fieldnames=headers)
        writer.writeheader()
       
        # iterate through the metrics
        for m in metricDict.keys():
            f = open(path.join(subj, metricDict[m]), "r")
            reader = csv.DictReader(f, delimiter=" ")
            l = reader.next()
           
            # remove non-numeric keys
            for v in l.keys():
                try:
                    int(v)
                except:
                    del(l[v])

            mDict = {v:l[v] for v in l.keys() if int(v) in self.c.G.nodes()}
            f.close()
           
            # normalise within metric
            meanMetric = np.mean([float(v) for v in mDict.values()])
            sdMetric = np.std([float(v) for v in mDict.values()])

            mDict = {str(v):(float(mDict[str(v)])-meanMetric)/sdMetric for v in mDict.keys()}
           
            mDict["Metric"] = m
           
            writer.writerow(mDict)
           
    def writeYMatrixIndividuals(self, metricDict, subjList, outFile="YmatrixInd.csv"):
        '''
        Collates metrics in to a matrix for use in partial least squares analysis.
        Note, the metricDict contains the metric name as a key and filename as
        the value. Takes metrics for individual subjects defined in the subject list.
        '''
        out = open(outFile, "wb")
        headers = ["Metric", "Subject"]
        headers.extend([str(v) for v in self.c.G.nodes()])
        writer = csv.DictWriter(out, fieldnames=headers)
        writer.writeheader()
       
        # iterate through the metrics
        for m in metricDict.keys():
            for subj in subjList:            
                f = open(path.join(subj, metricDict[m]), "r")
                reader = csv.DictReader(f, delimiter=" ")
                l = reader.next()
               
                # remove non-numeric keys
                for v in l.keys():
                    try:
                        int(v)
                    except:
                        del(l[v])
   
                mDict = {v:l[v] for v in l.keys() if int(v) in self.c.G.nodes()}
                f.close()
               
                # normalise within metric
                meanMetric = np.mean([float(v) for v in mDict.values()])
                sdMetric = np.std([float(v) for v in mDict.values()])
   
                mDict = {str(v):(float(mDict[str(v)])-meanMetric)/sdMetric for v in mDict.keys()}
               
                mDict["Metric"] = m
                mDict["Subject"] = subj
               
                writer.writerow(mDict)
