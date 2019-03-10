def phrase_search(object_list: list, search_string: str) -> int:
    if len(object_list) != 0:
        for obj in object_list:
            if obj['id'] > 0 and len(obj['phrase']) <= 120 and len(obj["slots"]) <= 50:
                first_brace = obj['phrase'].find('{')
                second_brace = obj['phrase'].rfind('}')
                if first_brace != -1 and second_brace != -1 and len(obj['slots']) > 0:
                    obj['slots'].insert(0, obj['phrase'][first_brace+1:second_brace])
                    for slot in obj['slots']:
                        pre = obj['phrase'][0:first_brace]
                        post = obj['phrase'][second_brace+1:len(obj['phrase'])]
                        phrase = pre + slot + post
                        if phrase == search_string:
                            return obj['id']
                elif obj['phrase'] == search_string:
                    return obj['id']
    return 0


if __name__ == "__main__":
    """ 
    len(object) != 0
    object["id"] > 0
    0 <= len(object["phrase"]) <= 120
    0 <= len(object["slots"]) <= 50
    """
    object = [
        {"id": 1, "phrase": "Hello world!", "slots": []},
        {"id": 2, "phrase": "I wanna {pizza}", "slots": ["pizza", "BBQ", "pasta"]},
        {"id": 3, "phrase": "Give me your power", "slots": ["money", "gun"]},
        {"id": 4, "phrase": "Give your {power}", "slots": []},
    ]

    assert phrase_search(object, 'I wanna pasta') == 2
    assert phrase_search(object, 'Give me your power') == 3
    assert phrase_search(object, 'Hello world!') == 1
    assert phrase_search(object, 'I wanna nothing') == 0
    assert phrase_search(object, 'Hello again world!') == 0
    assert phrase_search(object, 'I need your clothes, your boots & your motorcycle') == 0