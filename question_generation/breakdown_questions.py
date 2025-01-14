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
parser.add_argument('--input_scene_file', default='/Users/jessie/code/research/CLEVR_v1.0/scenes/CLEVR_val_scenes.json',
    help="JSON file containing ground-truth scene information for all images " +
         "from render_images.py")
parser.add_argument('--synonyms_json', default='synonyms.json',
    help="JSON file defining synonyms for parameter values")
# Output
parser.add_argument('--output_questions_file',
    default='../output/CLEVR_questions.json',
    help="The output file to write containing generated questions")

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

def generate_text(question, family_index_to_template, synonyms):
    # if there is a relate, then it is of a different type
    # filters and a count
    # filters, relate, and a count
    param_type_to_name = {'size':'<Z>', 'color':'<C>', 'material': '<M>', 'shape': '<S>', 'relate': '<R>'}
    param_type_to_name2 = {'size':'<Z2>', 'color':'<C2>', 'material': '<M2>', 'shape': '<S2>'}
    
    node_types = [node['type'] for node in question]
    # choose correct template
    if 'relate' in node_types and 'count' in node_types:
        template = family_index_to_template[72]
    elif 'count' in node_types:
        template = family_index_to_template[84]
    elif 'query_shape' in node_types:
        if 'relate' in node_types:
            template = family_index_to_template[77]            
        else:
            template = family_index_to_template[86]
    elif 'query_material' in node_types:
        if 'relate' in node_types:
            template = family_index_to_template[76]            
        else:
            template = family_index_to_template[87]
    elif 'query_color' in node_types:
        if 'relate' in node_types:
            template = family_index_to_template[75]            
        else:
            template = family_index_to_template[88]
    elif 'query_size' in node_types:
        if 'relate' in node_types:
            template = family_index_to_template[74]            
        else:
            template = family_index_to_template[89]


    # create list of params
    params = {}
    for p in template['params']:
        if p['type'] == 'Shape':
            params[p['name']] = 'thing'
        else:
            params[p['name']] = ''
    
    # fill out list of params
    relate = False
    for node in question:
        if node['side_inputs']:
            param_type = node['type'].split('_')
            if param_type[0] == 'relate':
                relate = True
                params[param_type_to_name[param_type[0]]] = node['side_inputs'][0]
            if param_type[0] == 'filter':
                if relate:
                    params[param_type_to_name2[param_type[1]]] = node['side_inputs'][0]
                else:
                    params[param_type_to_name[param_type[1]]] = node['side_inputs'][0]

    # use params to fill out template text
    text = random.choice(template['text'])
    for name, val in params.items():
        if val in synonyms:
            val = random.choice(synonyms[val])
        if name == '<S>' and val == '':
            val = 'object'
        text = text.replace(name, val)
        text = ' '.join(text.split())

    return text 

def create_subq(q, all_scenes, family_index_to_template, qfi, synonyms, metadata):
    image_filename = q['image_filename']
    # find scene
    for i, scene in enumerate(all_scenes):
        scene_fn = scene['image_filename']
        if scene_fn == image_filename:
            test_scene_struct = scene
            break
    subqs = []
    curr_subq = []
    curr_num = 0
    nodes = copy.deepcopy(q['program'])

    new_inds = []
    # qfi 0-8 from compare_integer.json, 9-24 from compare_integer.json
    if 0 <= qfi <=24: 
        for i in nodes:
            if i['type'] == 'scene':
                new_inds.append((len(subqs), 0))
                subqs.append([i])
            elif i['type'] in ['equal_color', 'equal_size', 'equal_material', 'equal_shape', 'greater_than', 'less_than', 'equal_integer']:
                break
            else:
                subq_id, input_new_ind = new_inds[i['inputs'][0]]
                new_inds.append((subq_id, input_new_ind+1))
                i['inputs'] = [input_new_ind] 
                subqs[subq_id].append(i)
    elif qfi == 31 or 64 <=qfi<=71:
        for i in nodes:
            if i['type'] == 'scene':
                if curr_subq:
                    subqs.append(curr_subq)
                curr_subq = []
                curr_num  = 0
                curr_subq.append(i)
            elif i['type'] in ['intersect', 'union']:
                if curr_subq:
                    subqs.append(curr_subq)
                resume_ind = nodes.index(i)
                break
            else:
                i['inputs'] = [curr_num]   
                curr_subq.append(i)
                curr_num += 1
        for subq in subqs:
            for i in nodes[resume_ind+1:]:
                new_node = copy.deepcopy(i)
                new_node['inputs'] = [len(subq)-1]
                subq.append(new_node)
        
    return_subqs = []
    for i, subq in enumerate(subqs):
        question = subq
        # print(question)
        answer = qeng.answer_question({'nodes':question}, metadata, test_scene_struct)
        # print(answer)
        text = generate_text(question, family_index_to_template, synonyms)
        new_subq = {'program':question, 'answer':answer, 'question':text}
        # print(text, answer)
        return_subqs.append({'question':text, 'answer':answer})
    return return_subqs

def main(args):
    # Load templates so we can extract family_index_to_template mapping
    num_loaded_templates = 0
    templates = {}
    family_index_to_template = {}
    for fn in TEMPLATE_ORDER:
        with open(os.path.join(args.template_dir, fn), 'r') as f:
            for i, template in enumerate(json.load(f)):
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

    # load scenes
    with open(args.input_scene_file, 'r') as f:
        scene_data = json.load(f)
        all_scenes = scene_data['scenes']
        scene_info = scene_data['info']

    subq_count = 0
    questions = []
    with open('/Users/jessie/code/research/CLEVR_v1.0/questions/CLEVR_val_questions.json', 'rb') as f:
        for q in ijson.items(f, 'questions.item'):
            qfi = q['question_family_index']
            if qfi == 31 or 64 <=qfi<=71:
                programs = q['program']
                for p in programs:
                    p['type'] = p.pop('function')
                    p['side_inputs'] = p.pop('value_inputs')
                # print(q['question'])
                q['subquestions'] = create_subq(q, all_scenes, family_index_to_template, qfi, synonyms, metadata)
                questions.append(q)
                subq_count += 1
            elif 0 <= qfi <= 24:
                # print(q)
                programs = q['program']
                for p in programs:
                    p['type'] = p.pop('function')
                    p['side_inputs'] = p.pop('value_inputs')
                # print(q['question'])
                subqs = create_subq(q, all_scenes, family_index_to_template, qfi, synonyms, metadata)
                if not subqs:
                    raise Exception("Question not decomposed properly")
                q['subquestions'] = subqs
                questions.append(q)
                subq_count += 1
            else:
                questions.append(q)

            
    print(subq_count)
    with open(args.output_questions_file, 'w') as f:
        print('Writing output to %s' % args.output_questions_file)
        json.dump({
            'info': scene_info,
            'questions': questions,
        }, f)


if __name__ == '__main__':
    main(parser.parse_args())
