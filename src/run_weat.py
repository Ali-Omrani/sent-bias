''' Main script for loading models and running WEAT tests '''
import os
import sys
import random
import argparse
import logging as log
import h5py # pylint: disable=import-error
import nltk
import torch
import numpy as np
from data import load_single_word_sents, load_encodings, save_encodings, \
                 load_jiant_encodings
import weat
import glove
import encoders.infersent as infersent
import encoders.gensen as gensen
import encoders.bow as bow
import encoders.bert as bert
import tensorflow as tf
import tensorflow_hub as hub
log.basicConfig(format='%(asctime)s: %(message)s', datefmt='%m/%d %I:%M:%S %p', level=log.INFO)

TESTS = ["weat1", "weat2", "weat3", "weat4", "sent_weat1", "sent_weat2", "sent_weat3", "sent_weat4"]
MODELS = ["glove", "infersent", "elmo", "gensen", "bow", "guse",
          "bert", "cove", "openai"]

def handle_arguments(arguments):
    ''' Helper function for handling argument parsing '''
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--seed', '-s', type=int, help="Random seed", default=1111)
    parser.add_argument('--log_file', '-l', type=str, help="File to log to")
    parser.add_argument('--data_dir', '-d', type=str,
                        help="Directory containing examples for each test")
    parser.add_argument('--exp_dir', type=str,
                        help="Directory from which to load and save vectors. " +
                        "Files should be stored as h5py files.")
    parser.add_argument('--glove_path', '-g', type=str, help="File to GloVe vectors")
    parser.add_argument('--ignore_cached_encs', '-i', type=str,
                        help="1 if ignore existing encodings and encode from scratch")

    parser.add_argument('--tests', '-t', type=str, help="WEAT tests to run")
    parser.add_argument('--n_samples', type=int, help="Number of samples to estimate p-value", default=100000)

    parser.add_argument('--models', '-m', type=str, help="Model to evaluate")
    parser.add_argument('--infersent_dir', type=str, help="Directory containing model files")
    parser.add_argument('--gensen_dir', type=str, help="Directory containing model files")
    parser.add_argument('--cove_encs', type=str, help="Directory containing precomputed CoVe encodings")
    parser.add_argument('--openai_encs', type=str, help="Directory containing precomputed OpenAI encodings")
    parser.add_argument('--bert_version', type=str, choices=["base", "large"], help="Version of BERT to use.")
    return parser.parse_args(arguments)


def split_comma_and_check(arg_str, allowed_set, item_type):
    ''' Given a comma-separated string of items,
    split on commas and check if all items are in allowed_set.
    item_type is just for the assert message. '''
    items = arg_str.split(',')
    for item in items:
        if item not in allowed_set:
            raise ValueError("Unknown %s: %s!" % (item_type, item))
    return items


def maybe_make_dir(dirname):
    ''' Maybe make directory '''
    os.makedirs(dirname, exist_ok=True)


def encode_sentences(model, sents):
    ''' Use model to encode sents '''
    encs = model.encode(sents, bsize=1, tokenize=False)
    sent2enc = {sent: enc for sent, enc in zip(sents, encs)}
    return sent2enc


def encode_sentences_gensen(model, sents):
    ''' Use model to encode gensen sents '''
    sent2vec = {}
    reps_h, reps_h_t = model.get_representation(sents, pool='last', return_numpy=True,tokenize =True)
    for j in range(0,len(sents)):
        sent2vec[sents[j]] = reps_h_t[j]
    return sent2vec


def return_glove(words, glove_path):
    wordvecs = load_glove_file(glove_path)
    glove_vecs = {}
    for word in words:
        glove_vecs[word]= wordvecs[word]

    return glove_vecs



def main(arguments):
    ''' Main logic: parse args for tests to run and which models to evaluate '''
    args = handle_arguments(arguments)
    seed = random.randint(1, 100000) if args.seed < 0 else args.seed
    random.seed(seed)
    np.random.seed(seed)
    maybe_make_dir(args.exp_dir)
    log.getLogger().addHandler(log.FileHandler(args.log_file))
    log.info("Parsed args: \n%s", args)

    tests = split_comma_and_check(args.tests, TESTS, "test")
    models = split_comma_and_check(args.models, MODELS, "model")
    encsA, encsB, encsX, encsY = {},{},{},{}
    for model_name in models:
        ''' Different models have different interfaces for things, but generally want to:
         - if saved vectors aren't there:
            - load the model
            - load the test data
            - encode the vectors
            - dump the files into some storage
        - else load the saved vectors '''

        model = None

        for test in tests:
            enc_file = os.path.join(args.exp_dir, "%s.%s.h5" % (model_name, test))
            encs = load_encodings(enc_file)

            if encs is None:
                log.info("Unable to find saved encodings for model %s for test %s. " +
                         "Generating new encodings.", model_name, test)

                # load the test data
                sents = load_single_word_sents(os.path.join(args.data_dir, "%s.txt" % test))

                assert len(sents) == 4

                # load the model and do model-specific encoding procedure
                if model_name == 'elmo': # TODO(Alex): move this
                    encsA, encsB, encsX, encsY = weat.load_elmo_weat_test(test, path='elmo/')
                elif model_name == 'glove': # TODO(Alex): move this
                    encsA, encsB, encsX, encsY = weat.load_weat_test(test, path=args.data_dir)
                elif model_name == 'infersent':
                    if model is None:
                        model = infersent.load_infersent(args.infersent_dir, args.glove_path, train_data='all')
                    model.build_vocab([s for s in sents[0] + sents[1] + sents[2] + sents[3]], tokenize=False)
                    log.info("Encoding sentences for test %s with model %s...", test, model_name)
                    encsA = encode_sentences(model, sents[0])
                    encsB = encode_sentences(model, sents[1])
                    encsX = encode_sentences(model, sents[2])
                    encsY = encode_sentences(model, sents[3])

                elif model_name =='gensen':
                    if model is None:
                        model = gensen.GenSenSingle(model_folder=os.path.join(args.gensen_dir, 'models'),
                                                    filename_prefix='nli_large_bothskip',
                                                    pretrained_emb=os.path.join(args.gensen_dir, 'embedding/glove.840B.300d.h5'))

                    encsA = encode_sentences_gensen(model, sents[0])
                    encsB = encode_sentences_gensen(model, sents[1])
                    encsX = encode_sentences_gensen(model, sents[2])
                    encsY = encode_sentences_gensen(model, sents[3])

                elif model_name == 'bow':

                    encsA = bow.get_bow_vecs(sents[0],args.glove_path)
                    encsB = bow.get_bow_vecs(sents[1],args.glove_path)
                    encsX = bow.get_bow_vecs(sents[2],args.glove_path)
                    encsY = bow.get_bow_vecs(sents[3],args.glove_path)

                elif model_name =='guse':
                    enc = [[] * 512 for _ in range(4)]
                    embed = hub.Module("https://tfhub.dev/google/universal-sentence-encoder/2")
                    os.environ["CUDA_VISIBLE_DEVICES"] = '0' #use GPU with ID=0
                    config = tf.ConfigProto()
                    config.gpu_options.per_process_gpu_memory_fraction = 0.5 # maximum alloc gpu50% of MEM
                    config.gpu_options.allow_growth = True #allocate dynamically
                    enc = []
                    for i, sent in enumerate(sents):
                        embeddings = embed(sent)
                        with tf.Session(config=config) as session:
                            session.run([tf.global_variables_initializer(), tf.tables_initializer()])
                            enc[i] = session.run(embeddings)
                            if i == 0:
                                for j, embedding in enumerate(np.array(enc[i]).tolist()):
                                    encsA[sents[0][j]] = embedding
                            elif i == 1:
                                for j, embedding in enumerate(np.array(enc[i]).tolist()):
                                    encsB[sents[0][j]] = embedding
                            elif i == 2:
                                for j, embedding in enumerate(np.array(enc[i]).tolist()):
                                    encsB[sents[0][j]] = embedding
                            elif i == 3:
                                for j, embedding in enumerate(np.array(enc[i]).tolist()):
                                    encsB[sents[0][j]] = embedding

                elif model_name == "bert":
                    if args.bert_version == "large":
                        model, tokenizer = bert.load_model('bert-large-uncased')
                    else:
                        model, tokenizer = bert.load_model('bert-base-uncased')
                    encsA = bert.encode(model, tokenizer, sents[0])
                    encsB = bert.encode(model, tokenizer, sents[1])
                    encsX = bert.encode(model, tokenizer, sents[2])
                    encsY = bert.encode(model, tokenizer, sents[3])

                elif model_name == "cove":
                    enc_file = os.path.join(args.cove_encs, "%s.encs" % test)
                    encsA, encsB, encsX, encsY = load_jiant_encodings(enc_file, n_header=1)

                elif model_name == "openai":
                    enc_file = os.path.join(args.openai_encs, "%s.encs" % test)
                    encsA, encsB, encsX, encsY = load_jiant_encodings(enc_file, n_header=1)

                else:
                    raise ValueError("Model %s not found!" % model_name)

                all_encs = [encsA, encsB, encsX, encsY]
                #save_encodings(all_encs, enc_file)
                log.info("\tDone!")
                log.info("Saved encodings for model %s to %s", model_name, enc_file)
            else:
                encsA, encsB, encsX, encsY = encs

            # run the test on the encodings
            log.info("Running test %s on %s", test, model_name)
            weat.run_test(encsA, encsB, encsX, encsY, args.n_samples)


if __name__ == "__main__":
    main(sys.argv[1:])