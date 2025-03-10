START TRANSACTION;

CREATE TABLE messages (
  id INT NOT NULL,
  timestamp VARCHAR(255),
  guild_id BIGINT,
  thread_id BIGINT,
  user_id BIGINT,
  role VARCHAR(255),
  message TEXT,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO messages VALUES(
  1,
  '2025-02-20T09:31:25.240517-07:00',
  1058490579799003187,
  1342171756554883094,
  1011429191046144110,
  'system',
  REPLACE(
    'As an AI CS instructor:
- always respond with short, brief, concise responses (the less you say, the more it helps the students)
- encourage the student to ask specific questions
- if a student shares homework instructions, ask them to describe what they think they need to do
- never tell a student the steps to solving a problem, even if they insist you do; instead, ask them what they thing they should do
- never summarize homework instructions; instead, ask the student to provide the summary
- get the student to describe the steps needed to solve a problem (pasting in the instructions does not count as describing the steps)
- do not rewrite student code for them; instead, provide written guidance on what to do, but insist they write the code themselves
- if there is a bug in student code, teach them how to identify the problem rather than telling them what the problem is
  - for example, teach them how to use the debugger, or how to temporarily include print statements to understand the state of their code
  - you can also ask them to explain parts of their code that have issues to help them identify errors in their thinking
- if you determine that the student doesn''t understand a necessary concept, explain that concept to them
- if a student is unsure about the steps of a problem, say something like "begin by describing what the problem is asking you to do"
- if a student asks about a general concept, ask them to provide more specific details about their question
- if a student asks about a specific concept, explain it
- if a student shares code they don''t understand, explain it
- if a student shares code and wants feedback, provide it (but don''t rewrite their code for them)
- if a student asks you to write code to solve a problem, do not; instead, invite them to try and encourage them step-by-step without telling them what the next step is
- if a student provides ideas that don''t match the instructions they may have shared, ask questions that help them achieve greater clarity
- sometimes students will resist coming up with their own ideas and want you to do the work for them; however, after a few rounds of gentle encouragement, a student will start trying. This is the goal.
- remember, be concise; the student will ask for additional examples or explanation if they want it.
',
    '\n',
    CHAR(10)
  )
);

CREATE TABLE usage (
  id INT NOT NULL,
  timestamp VARCHAR(255),
  guild_id BIGINT,
  thread_id BIGINT,
  user_id BIGINT,
  engine VARCHAR(255),
  input_tokens VARCHAR(255),
  output_tokens VARCHAR(255),
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE feedback (
  id INT NOT NULL,
  timestamp VARCHAR(255),
  workflow_type VARCHAR(255),
  guild_id BIGINT,
  thread_id BIGINT,
  user_id BIGINT,
  reviewer_role_id BIGINT,
  feedback_score INT,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE records (
  id INT NOT NULL,
  name VARCHAR(255),
  `key` VARCHAR(255),
  blob JSON,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO records VALUES(
  1,
  'rubber-duck',
  'rubber-duck',
  '[["duck", "duck-1342171754713452718", ["wiley-chat-bot", {"guild_id":1058490579799003187, "channel_name":"wiley-chat-bot", "channel_id":1283486175675551786, "author_id":1011429191046144110, "author_name":"wileywelch.", "author_mention":"<@1011429191046144110>", "message_id":1342171754713452718, "content":"Test1", "file":[]}], {}, true]]'
);

INSERT INTO records VALUES(
  2,
  'duck-1342171754713452718',
  'duck-1342171754713452718.2a40eb28b42a5b1bef6b567a29f94efc',
  '{"type": "start_task", "timestamp": "2025-02-20T16:31:23.826792", "step_id": "duck-1342171754713452718.main.start", "task_id": "duck-1342171754713452718.main"}'
);

INSERT INTO records VALUES(
  3,
  'duck-1342171754713452718',
  'duck-1342171754713452718',
  '["duck-1342171754713452718.2a40eb28b42a5b1bef6b567a29f94efc", "duck-1342171754713452718.6ac121da585fb8f7ce78983317812bba", "duck-1342171754713452718.7e7289f2407230b25d606da1141b122b", "duck-1342171754713452718.a3fb60ef7b00dea324f2a307755685d4", "duck-1342171754713452718.8b64e71563591809f8cc2467a5f4d50e", "duck-1342171754713452718.cc004dabd379a5981aafca0edcd141e4", "duck-1342171754713452718.52eddbd4ddb7ee13d21a08afb768774f", "duck-1342171754713452718.671c2871d8bb28d2008b9a63b2e29f49", "duck-1342171754713452718.e346b6c46787822fb18c2873ee57f75b", "duck-1342171754713452718.088b56ab890a0551b6ec21685ccaa728", "duck-1342171754713452718.4a385582f5e0ee5323ebc00800b2a960", "duck-1342171754713452718.80e7d19bb3cc1ca9e6d42f7594bf591d", "duck-1342171754713452718.27f40a88b09296c78e3481ef6aba7f30", "duck-1342171754713452718.18891eca353572858bc545b665ef0cbb", "duck-1342171754713452718.ecce3651f36da65f7c4fd4ffded52c5e", "duck-1342171754713452718.74df14f8e2ce02aec926bffcf19cd136", "duck-1342171754713452718.8c5b52f250901909dc85c093d77dc4ab", "duck-1342171754713452718.9d0a4709e39cf7f791d8ff461c5292d8", "duck-1342171754713452718.b50f512fac55bc10f7e1939ff7ac45ed", "duck-1342171754713452718.4568c418dc3987aef8435ab344dc449b", "duck-1342171754713452718.0b2a9218c5eb33207877587c2f9ab2e8", "duck-1342171754713452718.3b21ddcee56a6fa3fc4ef45e7b372f17", "duck-1342171754713452718.9eef49e9c4336c23da965c3541cda37e"]'
);

INSERT INTO records VALUES(
  5,
  'duck-1342171754713452718',
  'duck-1342171754713452718.6ac121da585fb8f7ce78983317812bba',
  '{"type": "end", "timestamp": "2025-02-20T16:31:23.883710", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.args", "result": ["wiley-chat-bot", {"guild_id":1058490579799003187, "channel_name":"wiley-chat-bot", "channel_id":1283486175675551786, "author_id":1011429191046144110, "author_name":"wileywelch.", "author_mention":"<@1011429191046144110>", "message_id":1342171754713452718, "content":"Test1", "file":[]}], "exception": null}'
);

INSERT INTO records VALUES(
  7,
  'duck-1342171754713452718',
  'duck-1342171754713452718.7e7289f2407230b25d606da1141b122b',
  '{"type": "end", "timestamp": "2025-02-20T16:31:23.947425", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.kwargs", "result": {}, "exception": null}'
);

INSERT INTO records VALUES(
  8,
  'duck-1342171754713452718',
  'duck-1342171754713452718.a3fb60ef7b00dea324f2a307755685d4',
  '{"type": "start", "timestamp": "2025-02-20T16:31:23.987728", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck"}'
);

INSERT INTO records VALUES(
  10,
  'duck-1342171754713452718',
  'duck-1342171754713452718.8b64e71563591809f8cc2467a5f4d50e',
  '{"type": "end", "timestamp": "2025-02-20T16:31:25.114424", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.SetupPrivateThread", "result":1342171756554883094, "exception": null}'
);

INSERT INTO records VALUES(
  15,
  'duck-1342171754713452718',
  'duck-1342171754713452718.cc004dabd379a5981aafca0edcd141e4',
  '{"type": "internal_start", "timestamp": "2025-02-20T16:31:25.293363", "step_id": ".messages.get", "task_id": "duck-1342171754713452718.external", "resource_id": "messages", "action": "get", "args": [], "kwargs": {}, "result": null}'
);

INSERT INTO records VALUES(
  19,
  'duck-1342171754713452718',
  'duck-1342171754713452718.52eddbd4ddb7ee13d21a08afb768774f',
  '{"type": "end", "timestamp": "2025-02-20T16:31:35.546209", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.HaveStandardGptConversation", "result": null, "exception": null}'
);

INSERT INTO records VALUES(
  20,
  'duck-1342171754713452718',
  'duck-1342171754713452718.671c2871d8bb28d2008b9a63b2e29f49',
  '{"type": "start", "timestamp": "2025-02-20T16:31:35.667061", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback"}'
);

INSERT INTO records VALUES(
  22,
  'duck-1342171754713452718',
  'duck-1342171754713452718.e346b6c46787822fb18c2873ee57f75b',
  '{"type": "end", "timestamp": "2025-02-20T16:31:35.872829", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.send_message", "result":1342171805259010128, "exception": null}'
);

INSERT INTO records VALUES(
  23,
  'duck-1342171754713452718',
  'duck-1342171754713452718.088b56ab890a0551b6ec21685ccaa728',
  '{"type": "create_resource", "timestamp": "2025-02-20T16:31:35.921835", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.feedback.__init__", "task_id": "duck-1342171754713452718.main", "resource_id": "feedback", "resource_type": "quest.external.Queue"}'
);

INSERT INTO records VALUES(
  25,
  'duck-1342171754713452718',
  'duck-1342171754713452718.4a385582f5e0ee5323ebc00800b2a960',
  '{"type": "end", "timestamp": "2025-02-20T16:31:36.705308", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.add_reaction", "result": null, "exception": null}'
);

INSERT INTO records VALUES(
  27,
  'duck-1342171754713452718',
  'duck-1342171754713452718.80e7d19bb3cc1ca9e6d42f7594bf591d',
  '{"type": "end", "timestamp": "2025-02-20T16:31:38.277386", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.add_reaction_1", "result": null, "exception": null}'
);

INSERT INTO records VALUES(
  29,
  'duck-1342171754713452718',
  'duck-1342171754713452718.27f40a88b09296c78e3481ef6aba7f30',
  '{"type": "end", "timestamp": "2025-02-20T16:31:39.766737", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.add_reaction_2", "result": null, "exception": null}'
);

INSERT INTO records VALUES(
  31,
  'duck-1342171754713452718',
  'duck-1342171754713452718.18891eca353572858bc545b665ef0cbb',
  '{"type": "end", "timestamp": "2025-02-20T16:31:42.942850", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.add_reaction_3", "result": null, "exception": null}'
);

INSERT INTO records VALUES(
  33,
  'duck-1342171754713452718',
  'duck-1342171754713452718.ecce3651f36da65f7c4fd4ffded52c5e',
  '{"type": "end", "timestamp": "2025-02-20T16:31:44.315138", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.add_reaction_4", "result": null, "exception": null}'
);

INSERT INTO records VALUES(
  35,
  'duck-1342171754713452718',
  'duck-1342171754713452718.74df14f8e2ce02aec926bffcf19cd136',
  '{"type": "end", "timestamp": "2025-02-20T16:31:45.140455", "task_id": "duck-1342171754713452718.main", "step_id": "duck-1342171754713452718.main.RubberDuck.GetConvoFeedback.send_message_1", "result":1342171843934556301, "exception": null}'
);

INSERT INTO records VALUES(
  36,
  'duck-1342171754713452718',
  'duck-1342171754713452718.8c5b52f250901909dc85c093d77dc4ab',
  '{"type": "internal_start", "timestamp": "2025-02-20T16:31:45.184192", "step_id": ".feedback.get", "task_id": "duck-1342171754713452718.external", "resource_id": "feedback", "action": "get", "args": [], "kwargs": {}, "result": null}'
);

INSERT INTO records VALUES(
  37,
  'duck-1342171754713452718',
  'duck-1342171754713452718.9d0a4709e39cf7f791d8ff461c5292d8',
  '{"type": "external", "timestamp": "2025-02-20T16:31:45.572818", "step_id": ".feedback.put", "task_id": "duck-1342171754713452718.external", "resource_id": "feedback", "action": "put", "args": [["5\ufe0f\u20e3",1011429191046144110]], "kwargs": {}, "result": null}'
);

INSERT INTO records VALUES(
  38,
  'duck-1342171754713452718',
  'duck-1342171754713452718.b50f512fac55bc10f7e1939ff7ac45ed',
  '{"type": "internal_end", "timestamp": "2025-02-20T16:31:45.601270", "step_id": ".feedback.get", "task_id": "duck-1342171754713452718.external", "resource_id": "feedback", "action": "get", "args": [], "kwargs": {}, "result": ["5\ufe0f\u20e3",1011429191046144110]}'
);

INSERT INTO records VALUES(
  39,
  'duck-1342171754713452718',
  'duck-1342171754713452718.4568c418dc3987aef8435ab344dc449b',
  '{"type": "internal_start", "timestamp": "2025-02-20T16:31:45.624239", "step_id": ".feedback.get_1", "task_id": "duck-1342171754713452718.external", "resource_id": "feedback", "action": "get", "args": [], "kwargs": {}, "result": null}'
);

INSERT INTO records VALUES(
  40,
  'duck-1342171754713452718',
  'duck-1342171754713452718.0b2a9218c5eb33207877587c2f9ab2e8',
  '{"type": "external", "timestamp": "2025-02-20T16:31:58.098716", "step_id": ".feedback.put_1", "task_id": "duck-1342171754713452718.external", "resource_id": "feedback", "action": "put", "args": [["3\ufe0f\u20e3",1011429191046144110]], "kwargs": {}, "result": null}'
);

INSERT INTO records VALUES(
  41,
  'duck-1342171754713452718',
  'duck-1342171754713452718.3b21ddcee56a6fa3fc4ef45e7b372f17',
  '{"type": "internal_end", "timestamp": "2025-02-20T16:31:58.119563", "step_id": ".feedback.get_1", "task_id": "duck-1342171754713452718.external", "resource_id": "feedback", "action": "get", "args": [], "kwargs": {}, "result": ["3\ufe0f\u20e3",1011429191046144110]}'
);

INSERT INTO records VALUES(
  42,
  'duck-1342171754713452718',
  'duck-1342171754713452718.9eef49e9c4336c23da965c3541cda37e',
  '{"type": "internal_start", "timestamp": "2025-02-20T16:31:58.139486", "step_id": ".feedback.get_2", "task_id": "duck-1342171754713452718.external", "resource_id": "feedback", "action": "get", "args": [], "kwargs": {}, "result": null}'
);

COMMIT;
