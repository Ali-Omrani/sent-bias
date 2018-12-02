# sent-bias

## Setup 

First, install Anaconda and a C++ compiler (for example, `g++`) if you
do not have them.  Then
use `environment.yml` to create a conda environment with all necessary
code dependencies: `conda env create -f environment.yml`.
Activate the environment with `source activate sentbias`.

Then, in the environment, download the NLTK punkt tokenization
resource:

```
python -c 'import nltk; nltk.download("punkt")'
```

You will also need to download pretrained model weights for each model
you want to test.  Instructions for each supported model are as
follows.

### GloVe 

Download and unzip the [GloVe Common Crawl 840B 300d
vectors](http://nlp.stanford.edu/data/glove.840B.300d.zip) from the
[Stanford NLP GloVe web
page](https://nlp.stanford.edu/projects/glove/).  Make note of the
path to the resultant text file.

### ELMo

ELMo weights will be downloaded and cached at runtime.  Set `ALLENNLP_CACHE_ROOT` in your environment to a directory you'd like them to be saved to; otherwise they will be saved to `~/.allennlp`.  For example, if using bash, run this before running ELMo bias tests or put it in your `~/.bashrc` and start a new shell session to run bias tests:

```
export ALLENNLP_CACHE_ROOT=/data/allennlp_cache
```

### Infersent

Download the model checkpoints from the [original repo](https://github.com/facebookresearch/InferSent) and put them in `sentbias/encoders`:

```
curl -Lo sentbias/encoders/infersent.allnli.pickle https://s3.amazonaws.com/senteval/infersent/infersent1.pkl
```

### GenSen

Download the model checkpoints.
Note, you need to process your GloVe word vectors into an HDF5 format. Run `scripts/glove2h5.py` in a directory containing the GloVe vectors.

## Running Bias Tests

We provide a script that demonstrates how to run the bias tests for each model.  To use it, minimally set the path to the GloVe vectors as `GLOVE_PATH` in a file called `user_config.sh`:
 
```
GLOVE_PATH=path/to/glove/vectors.txt
```
 
Then copy `scripts/run_tests.sh` to another location, edit as desired, and run it with `bash`.

### Details

To run bias tests directly, run `main` with one or more tests and one or more models.  Note that each model may require additional command-line flags specifying locations of resources and other options. For example, to run all tests against the bag-of-words (GloVe) and ELMo models:

```
python sentbias/main.py -m bow,elmo
    --glove_path path/to/glove/vectors.txt
```

Run `python sentbias/main.py --help` to see a full list of options.

## Code Tests

To run tests on the code do the following:

```
pytest
flake8
```

## TODO

- track down NaNs in GenSen [Shikha]: looks like the denominator (stddev) of the effect size is 0 because a lot of the vectors are the same...possibly a problem with OOV, but all these words should be in GloVe (base word representations used). Can you make sure the vocab expansion method they implemented is being used?
- add options for concatenation of GenSen models [Shikha]
- implement SkipThought [Shikha]
