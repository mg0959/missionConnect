$(document).ready(function() {
    $('.commentarea').keydown(function(event) {
        if (event.keyCode == 13) {
            this.form.submit();
            return false;
         }
    });

});

function testAJAX() {
  $.post('{{url_for("AJAX_test")}}', {}).done(function(args){
    alert(args['response']);
  }).fail(function(arg1, arg2, arg3){alert("failed: 1)"+arg1+" 2)"+arg2+" 3)"+arg3)});
}

function testAJAX2() {
  $.ajax({
    url: '{{url_for("AJAX_test")}}',
    type:'POST',
    data: {},
    success:function(result){alert('Sucessfully called');},
    error:function(exception){
      alert('Exception: '+exception);
      }
  })
}

function editFormShow(postBodyId, actionBtnId, postEditId) {
  $(actionBtnId).collapse("hide");
  $(postBodyId).collapse("hide");
  $(postEditId).collapse("show");
}

function editFormHide(postBodyId, actionBtnId, postEditId) {
  $(postEditId).collapse("hide");
  $(postBodyId).collapse("show");
  $(actionBtnId).collapse("show");}
  
function submitEditChanges(postId){
  $.post('{{url_for("updatePost")}}', {
    postObjId: postId,
    postBody: $('#textArea'+postId).val(),
    postType: $('#PTVal'+postId).val()
    }).done(function(){
    if ($('#PTVal'+postId).val() == "1") {
      $('#postBody'+ postId).text($('#textArea'+postId).val());
      $('#postTable'+ postId).removeClass("prayerRow");
    }
    else {
      if ($('#PTVal'+postId).val() == "3") {
        $('#postBody'+ postId).replaceWith("<p id='postBody"+postId+"'><strong>Pray:</strong> " + $('#textArea'+postId).val()+"</p>");
        $('#postTable'+ postId).addClass("prayerRow");
      }
    }
    editFormHide('#postBody'+ postId, '#actionBtn'+ postId, '#postEdit'+ postId);
  }).fail(function(){
    alert("Error: Could not contact server.");
    });
}
function deletePost(postID, postRowID, postDeletConfirmID) {
  $(postRowID).collapse('hide');
  $.post('{{url_for("deletePost")}}', {
    postObjID: postID
  }).done(function(){
    $(postDeletConfirmID).collapse('show');        
  }).fail(function(){
    alert("Error: Could not contact server.");
    $(postRowID).collapse('show');
    });
}

function updateSearchType(hiddenTag, buttonTxt, selection) {
  $(hiddenTag).val(selection);
  $(buttonTxt).text(selection);
}

function setPostType(checkType, postId){
    if (checkType == "1") {
        $('#radioPost'+postId).prop("checked", true);
        $('#PTVal'+postId).val("1");
    }
    else {
        if (checkType == "3") {
            $('#radioPray'+postId).prop("checked", true);
            $('#PTVal'+postId).val("3");
        }
        else {alert("ERROR in setting postType")}
    }
}


function ajaxAddPrayingUser(postId){
    $.post('{{url_for("addPrayingUser")}}', {
    postObjId: postId
    }).done(function(){
        prayerLink = document.getElementById("addPrayerLink"+postId);
        prayerLink.classList.remove("btn-default");
        prayerLink.classList.add("disabled", "btn-success");
        prayerLink.innerHTML = "<span class='glyphicon glyphicon-ok' aria-hidden='true'></span> I'm Praying";
        }
    ).fail(function(){
        alert("Error: Could not contact server.");}
    );
}

function ajaxRemovePrayingUser(postId){
    $.post('{{url_for("removePrayingUser")}}', {
    postObjId: postId
    }).done(function(){
        prayerRow = document.getElementById("prayerRow"+postId);
        prayerRow.parentNode.removeChild(prayerRow);
        }
    ).fail(function(){
        alert("Error: Could not contact server.");}
    );
}
