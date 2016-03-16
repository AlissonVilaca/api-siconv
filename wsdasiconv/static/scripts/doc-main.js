/*
    Fonte: Tema por Matt Graham https://github.com/mattgraham/Leap-Day
    Licença Creative Commons 3.0 Attribution
*/

var sectionHeight = function() {
  var total    = $(window).height(),
      $section = $('section').css('height','auto');

  if ($section.outerHeight(true) < total) {
    var margin = $section.outerHeight(true) - $section.height();
    $section.height(total - margin - 20);
  } else {
    $section.css('height','auto');
  }
}

$(window).resize(sectionHeight);

$(document).ready(function(){
  $("article > ul > li").each(function(){
    var id_secao = this.getAttribute("id");
    var nome_secao = $(this).find("h2").text().split(":")[1].trim();
    $("#side-menu ul").append("<li class='tag-h2'><a href='#" + id_secao + "'>" + nome_secao + "</a></li>");
    $("#side-menu ul li:first-child a").parent().addClass("active");
  });
  
  $("#side-menu ul li").on("click", "a", function(event) {
    var position = $($(this).attr("href")).offset().top;
    $("html, body").animate({scrollTop: position}, 400);
    $("#side-menu ul li a").parent().removeClass("active");
    $(this).parent().addClass("active");
    event.preventDefault();    
  });
  
  sectionHeight();
  
  $('img').load(sectionHeight);
});

fixScale = function(doc) {

  var addEvent = 'addEventListener',
      type = 'gesturestart',
      qsa = 'querySelectorAll',
      scales = [1, 1],
      meta = qsa in doc ? doc[qsa]('meta[name=viewport]') : [];

  function fix() {
    meta.content = 'width=device-width,minimum-scale=' + scales[0] + ',maximum-scale=' + scales[1];
    doc.removeEventListener(type, fix, true);
  }

  if ((meta = meta[meta.length - 1]) && addEvent in doc) {
    fix();
    scales = [.25, 1.6];
    doc[addEvent](type, fix, true);
  }

};
