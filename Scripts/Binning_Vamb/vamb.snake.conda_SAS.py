#!/usr/bin/env python

# set configurations
INDEX_SIZE = config.get("index_size", "12G")
MM_MEM = config.get("minimap_mem", "35gb")
MM_PPN = config.get("minimap_ppn", "10")
VAMB_MEM = config.get("vamb_mem", "20gb")
VAMB_PPN = config.get("vamb_ppn", "10")
CHECKM_MEM = config.get("checkm_mem", "25gb")
CHECKM_PPN = config.get("checkm_ppn", "10")
SAMPLE_DATA = config.get("sample_data", "samples2data.txt")
CONTIGS = config.get("contigs", "contigs.txt")
VAMB_PARAMS = config.get("vamb_params", "-o C -m 2000 --minfasta 500000")
VAMB_PRELOAD = config.get("vamb_preload", "")

# parse if GPUs is needed #
VAMB_split = VAMB_PPN.split(":") 
VAMB_threads = VAMB_split[0]

## read in sample information ##

# read in sample2path
IDS = []
sample2path = {}
fh_in = open(SAMPLE_DATA, 'r')
for line in fh_in:
    line = line.rstrip()
    fields = line.split('\t')
    IDS.append(fields[0])
    sample2path[fields[0]] = [fields[1], fields[2]]

# read in list of per-sample assemblies
contigs_list = []
fh_in = open(CONTIGS, 'r')
for line in fh_in:
    line = line.rstrip()
    contigs_list.append(line)


## start of snakemake rules ##
localrules: batch_check 
# targets
rule all:
    input:
        "jgi_matrix/jgi.abundance.dat",
        "vamb/clusters.tsv",
        #"vamb/checkm.results"

rule cat_contigs:
    input:
        contigs_list
    output:
        "contigs.flt.fna.gz"
    params:
        walltime="86400", nodes="1", ppn="1", mem="10gb"
    threads:
        int(1)
    log:
        "log/contigs/catcontigs.log"
    conda:
        "envs/vamb.yaml"
    shell:
        #"echo 'ml Anaconda3 ; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ; set -eu ;/data/umcg-tifn/Binning_vamb/Pipeline/Binning_env/bin/concatenate.py {output} {input} -m 2000' > {log}  ;\n"
        "ml Anaconda3 ; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ; set -eu ;\n"
        "/data/umcg-tifn/Binning_vamb/Pipeline/Binning_env/bin/concatenate.py {output} {input} -m 2000 2> {log} ;\n"
        "chgrp umcg-tifn {output}"

rule index:
    input:
        contigs = "contigs.flt.fna.gz"
    output:
        mmi = "contigs.flt.mmi"
    params:
        walltime="864000", nodes="1", ppn="1", mem="90gb"
    threads:
        int(1)
    log:
        "log/contigs/index.log"
    conda: 
        "envs/minimap2.yaml"
    shell:
        "ml Anaconda3; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ; set -eu  ;\n"
        "/data/umcg-tifn/Binning_vamb/Pipeline/Binning_env/bin/minimap2 -I {INDEX_SIZE} -d {output} {input} 2> {log} ;\n"
        "chgrp umcg-tifn {output}"

rule dict:
    input:
        contigs = "contigs.flt.fna.gz"
    output:
        dict = "contigs.flt.dict"
    params:
        walltime="864000", nodes="1", ppn="1", mem="10gb"
    threads:
        int(1)
    log:
        "log/contigs/dict.log"
    conda:
        "envs/samtools.yaml"
    shell:
        "ml Anaconda3 SAMtools/1.10-GCC-9.3.0; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/vamp ;set -eu ;\n"
        "/software/software/SAMtools/1.10-GCC-9.3.0/bin/samtools dict {input} | cut -f1-3 > {output} 2> {log} ;\n"
        "chgrp umcg-tifn {output}"

rule minimap:
    input:
        fq = lambda wildcards: sample2path[wildcards.sample],
        mmi = "contigs.flt.mmi",
        dict = "contigs.flt.dict"
    output:
        bam = temp("mapped/{sample}.bam")
    params:
        walltime="864000", nodes="1", ppn=MM_PPN, mem=MM_MEM
    threads:
        int(MM_PPN)
    log:
        "log/map/{sample}.minimap.log"
    conda:
        "envs/minimap2.yaml"
    shell:
        "ml Anaconda3 SAMtools/1.10-GCC-9.3.0; set +eu ;source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ;set -eu ;\n"
        '''/data/umcg-tifn/Binning_vamb/Pipeline/Binning_env/bin/minimap2 -t {threads} -ax sr {input.mmi} {input.fq} | grep -v "^@" | cat {input.dict} - | /software/software/SAMtools/1.10-GCC-9.3.0/bin/samtools view -F 3584 -b - > {output.bam} ;\n'''
        "chgrp umcg-tifn {output}"

rule sort_and_jgi:
    input:
        "mapped/{sample}.bam"
    output:
        sorted = temp("mapped/{sample}.sort.bam"),
	jgi = temp("jgi/{sample}.raw.jgi")
    params:
        walltime="864000", nodes="1", ppn="2", mem="15gb",
        prefix="mapped/tmp.{sample}"
    threads:
        int(2)
    log:
        sort = "log/map/{sample}.sort.log",
	jgi = "log/jgi/{sample}.jgi"
    conda:
        "envs/samtools.yaml"
    shell:
        "ml Anaconda3 SAMtools/1.10-GCC-9.3.0; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/vamp ;set -eu ;\n"
        "/software/software/SAMtools/1.10-GCC-9.3.0/bin/samtools sort {input} -T {params.prefix} --threads {threads} -m 3G -o {output.sorted} 2>{log.sort} ;\n"
        "jgi_summarize_bam_contig_depths --noIntraDepthVariance --outputDepth {output.jgi} {output.sorted} 2>{log.jgi}"

#rule jgi:
#    input:
#        bam = "mapped/{sample}.sort.bam"
#    output:
#        jgi = temp("jgi/{sample}.raw.jgi")
#    params:
#        walltime="864000", nodes="1", ppn="1", mem="10gb"
#    threads:
#        int(1)
#    log:
#        "log/jgi/{sample}.jgi"
#    conda:
#        "envs/metabat2.yaml"
#    shell:
#        "ml Anaconda3; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/vamp ;set -eu ;\n"
#        "jgi_summarize_bam_contig_depths --noIntraDepthVariance --outputDepth {output} {input} 2>{log} ;\n"
#         "chgrp umcg-tifn {output}"

rule cut_column1to3: 
    input:
        "jgi/%s.raw.jgi" % IDS[0] 
    output:
        "jgi/jgi.column1to3"
    params:
        walltime="86400", nodes="1", ppn="1", mem="1gb"
    log:
        "log/jgi/column1to3"
    shell:
        "ml Anaconda3; set +eu ;source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/vamp; set -eu ;\n" 
        "cut -f1-3 {input} > {output} 2>{log}"

rule cut_column4to5:
    input:
        "jgi/{sample}.raw.jgi"
    output:
        "jgi/{sample}.cut.jgi"
    params:
        walltime="86400", nodes="1", ppn="1", mem="1gb"
    log:
        "log/jgi/{sample}.cut.log"
    shell: 
        "ml Anaconda3; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env; source activate /data/umcg-tifn/Binning_vamb/Pipeline/vamp; set -eu ;\n"
        "cut -f1-3 --complement {input} > {output} 2>{log}"

rule paste_abundances:
    input:
        column1to3="jgi/jgi.column1to3",
        data=expand("jgi/{sample}.cut.jgi", sample=IDS)
    output:
        "jgi_matrix/jgi.abundance.dat" 
    params:
        walltime="86400", nodes="1", ppn="1", mem="1gb"
    log:
        "log/jgi/paste_abundances.log"
    shell: 
        "paste {input.column1to3} {input.data} > {output} 2>{log}" 

rule vamb:
    input:
        jgi = "jgi_matrix/jgi.abundance.dat",
        contigs = "contigs.flt.fna.gz"
    output:
        "vamb/clusters.tsv",
        "vamb/latent.npz",
        "vamb/lengths.npz",
        "vamb/log.txt",
        "vamb/model.pt",
        "vamb/mask.npz",
        "vamb/tnf.npz"
    params:
        walltime="86400", nodes="1", ppn=VAMB_PPN, mem=VAMB_MEM
    log:
        "log/vamb/vamb.log"
    threads:
        int(VAMB_threads)
    conda:
        "envs/vamb.yaml"
    shell:
        "ml Anaconda3; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env; set -eu ; \n" #source activate /groups/umcg-lld/tmp01/other-users/umcg-sandreusanchez/Binning_HIV ;\n"
        #"{VAMB_PRELOAD} ;\n"
        #"rm -rf vamb; \n"
        "/data/umcg-tifn/Binning_vamb/Pipeline/Binning_env/bin/vamb --outdir vamb --fasta {input.contigs} --jgi {input.jgi} {VAMB_PARAMS} 2>{log} ;\n"
        "chgrp umcg-tifn {output}"

rule batch_check:
     #Written by Sergio Andreu, this is **not** proper snakemake and is a hack to get the checkm step done in batches
     input: "vamb/clusters.tsv"
     output: touch("vamb/checkm.results")
     shell:
         "ml Anaconda3 ; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env; set -eu  ; python Run_CheckM_batch.py"


rule checkm:
    input:
        "vamb/clusters.tsv"
    output:
        "vamb/checkm.results"
    params:
        walltime="86400", nodes="1", ppn=CHECKM_PPN, mem=CHECKM_MEM,
        bins = "vamb/bins",
        outdir = "vamb/checkm.outdir"
    log:
        "log/vamb/checkm.log"
    threads:
        int(CHECKM_PPN)
    conda:
        "envs/checkm.yaml"
    shell:
        "ml Anaconda3; set +eu ; source activate /data/umcg-tifn/Binning_vamb/Pipeline/Binning_env; source activate /data/umcg-tifn/Binning_vamb/Pipeline/vamp ;set -eu  ;\n"
        "checkm lineage_wf -f {output} -t {threads} -x fna {params.bins} {params.outdir} 2>{log}"
