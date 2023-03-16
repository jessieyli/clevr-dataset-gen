import ijson
import argparse
import os
import json
import copy
import random

import question_engine as qeng

parser = argparse.ArgumentParser()
parser.add_argument('--questions_file',
    default='../output/CLEVR_v1.0/questions/CLEVR_val_questions.json')
parser.add_argument('--template_dir', default='CLEVR_1.0_templates/')
parser.add_argument('--num_samples', type=int, default=5)
parser.add_argument('--metadata_file', default='metadata.json',
    help="JSON file containing metadata about functions")
# parser.add_argument('--input_scene_file', default='../output/CLEVR_scenes.json',
#     help="JSON file containing ground-truth scene information for all images " +
#          "from render_images.py")
parser.add_argument('--input_scene_file', default='/Users/jessie/code/research/CLEVR_v1.0/scenes/CLEVR_val_scenes.json',
    help="JSON file containing ground-truth scene information for all images " +
         "from render_images.py")
parser.add_argument('--synonyms_json', default='synonyms.json',
    help="JSON file defining synonyms for parameter values")

TEMPLATE_ORDER = [
    'compare_integer.json',
    'comparison.json',
    'three_hop.json',
    'single_and.json',
    'same_relate.json',
    'single_or.json',
    'one_hop.json',
    'two_hop.json',
    'zero_hop.json',
]


def generate_text(template, params, synonyms):
    vals = {}
    for p in params:
        vals[params[p][0]] = params[p][1]
    
    text = random.choice(template['text'])
    for name, val in vals.items():
      if val in synonyms:
        val = random.choice(synonyms[val])
      if name == '<S>' and val == '':
          val = 'object'
      text = text.replace(name, val)
      text = ' '.join(text.split())
    
    # text = replace_optionals(text)
    # text = ' '.join(text.split())
    # text = other_heuristic(text, state['vals'])
    # text_questions.append(text)

    return text

def create_subq(q, all_scenes, family_index_to_template, synonyms, metadata):
    image_filename = q['image_filename']
    # TODO: find scene
    for i, scene in enumerate(all_scenes):
        scene_fn = scene['image_filename']
        if scene_fn == image_filename:
            test_scene_struct = scene
            break
    subqs = []
    curr_subq = []
    curr_num = 0
    nodes = copy.deepcopy(q['program'])
    #TODO: load params
    # params = [{'type': 'Size', 'name': '<Z>'}, {'type': 'Color', 'name': '<C>'}, {'type': 'Material', 'name': '<M>'}, {'type': 'Shape', 'name': '<S>'}]
    vals = {'size':['<Z>',""], 'color':['<C>', ""], 'material': ['<M>',""], 'shape': ['<S>',""]}
    for i in nodes:
        if i['type'] == 'scene':
            if curr_subq:
                subqs.append([curr_subq, vals])
            curr_subq = []
            curr_num  = 0
            vals = {'size':['<Z>',""], 'color':['<C>', ""], 'material': ['<M>',""], 'shape': ['<S>',""]}
            curr_subq.append(i)
        elif i['type'] in ['greater_than', 'less_than', 'equal_integer']:
            if curr_subq:
                subqs.append([curr_subq, vals])
            break
        else:
            i['inputs'] = [curr_num]
            param_type = i['type'].split('_')
            if param_type[0] =='filter':
                vals[param_type[1]][1] = i['side_inputs'][0]
            curr_subq.append(i)
            curr_num += 1
    
    for i, subq in enumerate(subqs):
        question = subq[0]
        vals = subq[1]
        text = generate_text(family_index_to_template[84], vals, synonyms)
        # print(text)
        answer = qeng.answer_question({'nodes':question}, metadata, test_scene_struct)
        new_subq = {'program':question, 'answer':answer, 'question':text}
        print(text, answer)
        # test_q['sub_questions'].append({})

def main(args):
    # Load templates so we can extract family_index_to_template mapping
    num_loaded_templates = 0
    templates = {}
    family_index_to_template = {}
    for fn in TEMPLATE_ORDER:
        with open(os.path.join(args.template_dir, fn), 'r') as f:
            base = os.path.splitext(fn)[0]
            for i, template in enumerate(json.load(f)):
                # if fn == 'one_hop.json':
                #     print(num_loaded_templates)
                family_index_to_template[num_loaded_templates] = template
                num_loaded_templates += 1
                key = (fn, i)
                templates[key] = template
    print('Read %d templates from disk' % num_loaded_templates)

    # load metadata
    with open(args.metadata_file, 'r') as f:
        metadata = json.load(f)
    with open(args.synonyms_json, 'r') as f:
        synonyms = json.load(f)

    # load test scene
    with open(args.input_scene_file, 'r') as f:
        scene_data = json.load(f)
        all_scenes = scene_data['scenes']
        scene_info = scene_data['info']

    for i, scene in enumerate(all_scenes):
        scene_fn = scene['image_filename']
        if scene_fn == 'CLEVR_val_000010.png':
            test_scene_struct = scene
            break

        scene_struct = scene

    and_qs = []
    subqs = []
    subq_count = 0
    with open('/Users/jessie/code/research/CLEVR_v1.0/questions/CLEVR_val_questions.json', 'rb') as f:
        for q in ijson.items(f, 'questions.item'):
            qfi = q['question_family_index']
            # if qfi == 76:
            #     print("one hop!")
            #     print(q)
            #     break
            # if 31 <= qfi <= 35:
            #     print("simple and")
            if 0 <= qfi <= 2:
                print("compare_integer")
                print(q)
                template = family_index_to_template[qfi]
                print()
                # print(template)
                # for t in template['text']:
                #     print(t)
                # print()
                # print(template['nodes'])
                # convert p in programs to 'type' instead of 'function'...
                programs = q['program']
                for p in programs:
                    p['type'] = p.pop('function')
                    p['side_inputs'] = p.pop('value_inputs')
                    
                create_subq(q, all_scenes, family_index_to_template, synonyms, metadata)
                subq_count += 1
                # test_q = {'nodes':q['program']}
                
                # curr_subq = []
                # curr_num = 0
                # nodes = copy.deepcopy(q['program'])
                # #TODO: load params
                # params = [{'type': 'Size', 'name': '<Z>'}, {'type': 'Color', 'name': '<C>'}, {'type': 'Material', 'name': '<M>'}, {'type': 'Shape', 'name': '<S>'}]
                
                # vals = {'size':['<Z>',""], 'color':['<C>', ""], 'material': ['<M>',""], 'shape': ['<S>',""]}
                # for i in nodes:
                #     if i['type'] == 'scene':
                #         if curr_subq:
                #             subqs.append([curr_subq, vals])
                #         curr_subq = []
                #         curr_num  = 0
                #         vals = {'size':['<Z>',""], 'color':['<C>', ""], 'material': ['<M>',""], 'shape': ['<S>',""]}
                #         curr_subq.append(i)
                #     elif i['type'] in ['greater_than', 'less_than', 'equal_integer']:
                #         if curr_subq:
                #             subqs.append([curr_subq, vals])
                #         break
                #     else:
                #         i['inputs'] = [curr_num]
                #         param_type = i['type'].split('_')
                #         if param_type[0] =='filter':
                #             vals[param_type[1]][1] = i['side_inputs'][0]
                #         curr_subq.append(i)
                #         curr_num += 1
                
                # print(qeng.answer_question())
                # break
                # and_qs.append(q)
    # print(test_q)
    # # print(subqs)
    # print(qeng.answer_question(test_q, metadata, test_scene_struct))
    # test_q['sub_questions'] = []
    # for i, subq in enumerate(subqs):
    #     question = subq[0]
    #     vals = subq[1]
    #     text = generate_text(family_index_to_template[84], vals, synonyms)
    #     print(text)
    #     answer = qeng.answer_question({'nodes':question}, metadata, test_scene_struct)
    #     print(f"sub-q {i}: {answer}")
    #     test_q['sub_questions'].append({})
    # 8451
    # print(len(and_qs))
    print(subq_count)


if __name__ == '__main__':
    main(parser.parse_args())
