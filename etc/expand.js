var fs = require('fs');
var handlebars = require('handlebars');
var config_str = fs.readFileSync(process.argv[2], encoding='utf-8');
var config = JSON.parse(config_str);
var template_str = fs.readFileSync(process.argv[3], encoding='utf-8');
var template = handlebars.compile(template_str, {strict:true});
var runtime_config_str = '';
process.stdin.setEncoding('utf8');
process.stdin.on('readable', function() {
    var fragment = process.stdin.read();
    if (fragment !== null)
        runtime_config_str += fragment;
});
process.stdin.on('end', gotRuntimeConfigStr);
function gotRuntimeConfigStr() {
    var runtime_config = JSON.parse(runtime_config_str);
    for (var key in runtime_config)
        config[key] = config[key] || runtime_config[key];
    var expansion = template(config);
    process.stdout.write(expansion);
}
